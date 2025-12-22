"""Interview Service - FastAPI application with WebSocket support."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import asyncio
import time
from typing import Dict, Optional, Any
import re

# Security helper: Sanitize error messages to prevent secret exposure
def sanitize_error_message(error: Exception) -> str:
    """Remove sensitive information from error messages."""
    msg = str(error)
    # Remove potential credential data
    sensitive_patterns = [
        r'private_key["\']?\s*[:=]\s*["\'][^"\']+["\']',
        r'client_email["\']?\s*[:=]\s*["\'][^"\']+["\']',
        r'project_id["\']?\s*[:=]\s*["\'][^"\']+["\']',
        r'-----BEGIN.*?-----END[^-]+-----',
        r'File\s+\{[^}]+\}',
    ]
    for pattern in sensitive_patterns:
        msg = re.sub(pattern, '[REDACTED]', msg, flags=re.IGNORECASE | re.DOTALL)
    return msg

from shared.config.settings import settings
from shared.auth.firebase_auth import get_current_user
from shared.db.redis_client import redis_client
from shared.db.firestore_client import firestore_client
from interview_service.models import (
    StartInterviewRequest, StartInterviewResponse, SkillWeightResponse,
    Answer, AnswerResponse, InterviewRole, InterviewPhase, InterviewFlowState, InterviewStatus
)
from interview_service.resume_analyzer import get_resume_data
from interview_service.skill_weighting import calculate_skill_weights, distribute_questions
from interview_service.interview_state import (
    create_interview_state, load_interview_state,
    start_interview, complete_interview, add_answer_to_state,
    save_interview_state, save_interview_state_to_firestore
)
from interview_service.adaptive_flow import calculate_progress
from interview_service.phased_flow import select_next_question_phased, update_phase_question_count
from interview_service.answer_evaluator import evaluate_answer
from interview_service.conversational_framing import get_candidate_name_safely
from interview_service.resume_analyzer import get_resume_data
from interview_service.websocket_handler import InterviewWebSocketHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for FastAPI app."""
    # Startup
    # Ensure Firebase is initialized before anything else
    try:
        from shared.auth.firebase_auth import initialize_firebase
        initialize_firebase()
        logger.info("✅ Firebase initialized during startup")
    except Exception as e:
        logger.error(f"❌ Firebase initialization failed during startup: {type(e).__name__}: {str(e)[:200]}")
        # Continue anyway - individual operations will handle errors
    
    await redis_client.connect()
    logger.info("Interview Service started")
    yield
    # Shutdown
    await redis_client.disconnect()
    logger.info("Interview Service stopped")


app = FastAPI(
    title="MockDay Interview Service",
    description="Real-time adaptive interview service with WebSocket support",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - use environment-based origins in production
cors_origins = settings.cors_origins if hasattr(settings, 'cors_origins') else settings.ALLOWED_ORIGINS
logger.info(f"🔒 CORS allowed origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections manager
class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.sent_question_ids: Dict[str, str] = {}  # Track which question_id was last sent per interview
        self.last_ping_time: Dict[str, float] = {}  # Track last ping time per interview to prevent timeout
    
    async def connect(self, interview_id: str, websocket: WebSocket):
        """Accept WebSocket connection."""
        # Close existing connection for this interview if any
        if interview_id in self.active_connections:
            try:
                await self.active_connections[interview_id].close()
            except:
                pass
            del self.active_connections[interview_id]
            # Don't clear sent_question_ids - we want to remember which question was sent
        
        await websocket.accept()
        self.active_connections[interview_id] = websocket
        logger.info(f"WebSocket connected for interview: {interview_id} (Total connections: {len(self.active_connections)})")
    
    def disconnect(self, interview_id: str):
        """Remove WebSocket connection and cleanup all tracking data."""
        if interview_id in self.active_connections:
            del self.active_connections[interview_id]
        # Clean up ping tracking to stop keepalive warnings
        if interview_id in self.last_ping_time:
            del self.last_ping_time[interview_id]
        # Clean up sent question IDs
        if interview_id in self.sent_question_ids:
            del self.sent_question_ids[interview_id]
        logger.info(f"WebSocket disconnected and cleaned up for interview: {interview_id} (Total connections: {len(self.active_connections)})")
    
    def mark_question_sent(self, interview_id: str, question_id: str):
        """Mark that a specific question has been sent."""
        self.sent_question_ids[interview_id] = question_id
    
    def has_question_been_sent(self, interview_id: str, question_id: str) -> bool:
        """Check if a specific question has been sent."""
        return self.sent_question_ids.get(interview_id) == question_id
    
    def get_last_sent_question_id(self, interview_id: str) -> Optional[str]:
        """Get the last sent question ID for an interview."""
        return self.sent_question_ids.get(interview_id)
    
    async def send_message(self, interview_id: str, message: dict):
        """Send message to WebSocket client."""
        if interview_id not in self.active_connections:
            logger.warning(f"Attempted to send message to disconnected interview: {interview_id}")
            return False
        
        websocket = self.active_connections[interview_id]
        try:
            # CRITICAL: Ensure message is valid JSON before sending
            import json
            try:
                json_str = json.dumps(message)
                # Verify it's valid JSON by parsing it back
                json.loads(json_str)
            except (TypeError, ValueError) as json_err:
                # Python's json module raises TypeError/ValueError for encoding errors, not JSONEncodeError
                # JSONDecodeError only exists for json.loads(), not json.dumps()
                logger.error(f"[Send Message] Invalid JSON for {interview_id}: {json_err}, message type: {type(message)}, message keys: {list(message.keys()) if isinstance(message, dict) else 'N/A'}")
                return False
            
            await websocket.send_json(message)
            return True
        except RuntimeError as e:
            # Connection is closed - this is expected in some cases
            error_msg = str(e)
            if "close message has been sent" in error_msg or "Cannot call" in error_msg:
                logger.debug(f"Connection already closed for {interview_id}: {e}")
            else:
                logger.warning(f"RuntimeError sending message to {interview_id}: {e}")
            # CRITICAL: Don't call disconnect() here - it removes from manager and causes "replaced by new connection" message
            # The receive loop will handle cleanup when it detects the connection is closed
            # Just return False to indicate send failed
            return False
        except WebSocketDisconnect:
            # Client disconnected normally
            logger.debug(f"Client disconnected for {interview_id}")
            # CRITICAL: Don't call disconnect() here - let receive loop handle cleanup
            # Calling disconnect() causes false "replaced by new connection" messages
            return False
        except Exception as e:
            logger.error(f"Error sending message to {interview_id}: {e}", exc_info=True)
            # CRITICAL: Don't call disconnect() here - it causes false "replaced by new connection" messages
            # The receive loop will detect the connection is closed and handle cleanup
            return False


manager = ConnectionManager()
websocket_handler = InterviewWebSocketHandler(manager)


# ============================================================================
# Health Check
# ============================================================================
@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint called")
    return {"message": "MockDay API", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check called")
    
    # Check Firebase status
    firebase_status = "unknown"
    try:
        from firebase_admin import get_app
        app = get_app()
        firebase_status = "initialized"
    except ValueError:
        firebase_status = "not_initialized"
    except Exception as e:
        firebase_status = f"error: {type(e).__name__}"
    
    return {
        "status": "ok",
        "service": "interview-service",
        "firebase": firebase_status
    }


# ============================================================================
# Profile Endpoints (Migrated from Flask)
# ============================================================================
@app.get("/api/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    """Get user profile with Redis caching."""
    try:
        user_id = user["uid"]
        
        # Try Redis cache first (fast)
        cache_key = f"user_profile:{user_id}"
        try:
            cached_profile = await redis_client.get(cache_key)
            if cached_profile:
                logger.debug(f"Profile cache hit for user: {user_id}")
                # Convert datetime to ISO format if present
                if "createdAt" in cached_profile and not isinstance(cached_profile["createdAt"], str):
                    cached_profile["createdAt"] = cached_profile["createdAt"].isoformat()
                if "updatedAt" in cached_profile and not isinstance(cached_profile["updatedAt"], str):
                    cached_profile["updatedAt"] = cached_profile["updatedAt"].isoformat()
                return cached_profile
        except Exception as e:
            logger.debug(f"Redis cache read failed (non-critical): {e}")
        
        # Fallback to Firestore (slower)
        profile = await firestore_client.get_document("users", user_id)
        if not profile:
            return {}
        
        # Convert datetime to ISO format if present
        if "createdAt" in profile and hasattr(profile["createdAt"], "isoformat"):
            profile["createdAt"] = profile["createdAt"].isoformat()
        if "updatedAt" in profile and hasattr(profile["updatedAt"], "isoformat"):
            profile["updatedAt"] = profile["updatedAt"].isoformat()
        
        # Cache in Redis (15 minutes TTL)
        try:
            profile_dict = profile.copy()
            await redis_client.set(cache_key, profile_dict, expire=900)
        except Exception as e:
            logger.debug(f"Redis cache write failed (non-critical): {e}")
        
        return profile
    except Exception as e:
        logger.error(f"Error getting profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch profile")


@app.put("/api/profile")
async def update_profile(
    profile_data: Dict[str, Any],
    user: dict = Depends(get_current_user)
):
    """Update user profile."""
    try:
        user_id = user["uid"]
        allowed_fields = {
            'name', 'location', 'experienceLevel', 'linkedinUrl', 'bio',
            'experiences', 'educations', 'skills'
        }
        update_data = {k: v for k, v in profile_data.items() if k in allowed_fields}
        
        # Add updated timestamp
        from datetime import datetime, timezone
        update_data['updatedAt'] = datetime.now(timezone.utc)
        
        # Update document
        success = await firestore_client.set_document("users", user_id, update_data, merge=True)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update profile")
        
        # Invalidate Redis cache (will be refreshed on next read)
        cache_key = f"user_profile:{user_id}"
        try:
            await redis_client.delete(cache_key)
        except Exception as e:
            logger.debug(f"Redis cache delete failed (non-critical): {e}")
        
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        logger.error(f"Error updating profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update profile")


# ============================================================================
# Email Verification Endpoints
# ============================================================================
@app.get("/api/auth/email-verification-status")
async def get_email_verification_status(user: dict = Depends(get_current_user)):
    """Check if user's email is verified."""
    try:
        user_id = user["uid"]
        email = user.get("email")
        
        # Get Firebase Auth user to check email verification status
        from firebase_admin import auth as firebase_auth
        from datetime import datetime, timezone
        try:
            firebase_user = firebase_auth.get_user(user_id)
            email_verified = firebase_user.email_verified
            
            # Also check Firestore for verification status (for backwards compatibility)
            profile = await firestore_client.get_document("users", user_id)
            firestore_verified = profile.get("emailVerified", False) if profile else False
            
            # Email is verified if either Firebase Auth or Firestore says so
            is_verified = email_verified or firestore_verified
            
            # Update Firestore if Firebase Auth says verified but Firestore doesn't
            if email_verified and not firestore_verified:
                await firestore_client.set_document(
                    "users", 
                    user_id, 
                    {"emailVerified": True, "emailVerifiedAt": datetime.now(timezone.utc)}, 
                    merge=True
                )
            
            return {
                "email": email,
                "emailVerified": is_verified,
                "emailVerifiedAt": profile.get("emailVerifiedAt") if profile else None
            }
        except Exception as e:
            logger.error(f"Error checking Firebase Auth user: {e}", exc_info=True)
            # Fallback to Firestore only
            profile = await firestore_client.get_document("users", user_id)
            return {
                "email": email,
                "emailVerified": profile.get("emailVerified", False) if profile else False,
                "emailVerifiedAt": profile.get("emailVerifiedAt") if profile else None
            }
    except Exception as e:
        logger.error(f"Error getting email verification status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check email verification status")


@app.post("/api/auth/verify-email")
async def verify_email(
    verification_data: Dict[str, Any],
    user: dict = Depends(get_current_user)
):
    """Mark email as verified (called after user clicks verification link)."""
    try:
        user_id = user["uid"]
        
        # Update Firestore with verification status
        from datetime import datetime, timezone
        update_data = {
            "emailVerified": True,
            "emailVerifiedAt": datetime.now(timezone.utc)
        }
        
        success = await firestore_client.set_document("users", user_id, update_data, merge=True)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update verification status")
        
        # Invalidate profile cache
        cache_key = f"user_profile:{user_id}"
        try:
            await redis_client.delete(cache_key)
        except Exception as e:
            logger.debug(f"Redis cache delete failed (non-critical): {e}")
        
        return {"success": True, "message": "Email verified successfully"}
    except Exception as e:
        logger.error(f"Error verifying email: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to verify email")


# ============================================================================
# Resume Endpoints (Migrated from Flask)
# ============================================================================
@app.get("/api/resumes")
async def list_resumes(user: dict = Depends(get_current_user)):
    """List user resumes with Redis caching."""
    try:
        user_id = user["uid"]
        
        # Try Redis cache first (fast)
        cache_key = f"user_profile:{user_id}"
        try:
            cached_profile = await redis_client.get(cache_key)
            if cached_profile:
                logger.debug(f"Resume list cache hit for user: {user_id}")
                resumes = cached_profile.get("resumes", [])
                return resumes
        except Exception as e:
            logger.debug(f"Redis cache read failed (non-critical): {e}")
        
        # Fallback to Firestore (slower)
        profile = await firestore_client.get_document("users", user_id)
        if not profile:
            return []
        
        resumes = profile.get("resumes", [])
        
        # Cache in Redis (15 minutes TTL)
        try:
            await redis_client.set(cache_key, profile, expire=900)
        except Exception as e:
            logger.debug(f"Redis cache write failed (non-critical): {e}")
        
        return resumes
    except Exception as e:
        logger.error(f"Error listing resumes: {e}")
        logger.error(f"Error listing resumes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list resumes")


# ============================================================================
# Reports Endpoints
# ============================================================================
@app.get("/api/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    """List user reports with Redis caching."""
    try:
        user_id = user["uid"]
        
        # Try Redis cache first (fast)
        cache_key = f"user_reports:{user_id}"
        try:
            cached_reports = await redis_client.get(cache_key)
            if cached_reports:
                logger.debug(f"Reports list cache hit for user: {user_id}")
                return cached_reports
        except Exception as e:
            logger.debug(f"Redis cache read failed (non-critical): {e}")
        
        # Fetch reports from Firestore
        reports = await firestore_client.query_collection(
            collection="reports",
            filters=[("user_id", "==", user_id)],
            order_by="created_at",  # Most recent first
            order_direction="DESCENDING",
            limit=100  # Limit to last 100 reports
        )
        
        # Format reports for frontend (extract key fields)
        formatted_reports = []
        for report_doc in reports:
            report_data = report_doc.get("report_data", {})
            formatted_reports.append({
                "report_id": report_doc.get("report_id"),
                "interview_id": report_doc.get("interview_id"),
                "role": report_doc.get("role"),
                "overall_score": report_doc.get("overall_score", report_data.get("overall_score", 0)),
                "created_at": report_doc.get("created_at"),
                "total_questions": report_data.get("total_questions", 0),
                "recommendation": report_data.get("recommendation", "maybe")
            })
        
        # Cache in Redis (15 minutes TTL)
        try:
            await redis_client.set(cache_key, formatted_reports, expire=900)
        except Exception as e:
            logger.debug(f"Redis cache write failed (non-critical): {e}")
        
        return formatted_reports
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        logger.error(f"Error listing reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list reports")


@app.post("/api/resumes/upload")
async def upload_and_parse_resume(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """
    Upload resume file, parse it immediately, and store parsed data.
    This endpoint handles the actual file upload and parsing.
    """
    try:
        user_id = user["uid"]
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file size (5MB limit)
        file_content = await file.read()
        if len(file_content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
        
        # Validate file type
        allowed_extensions = {".pdf", ".doc", ".docx", ".txt"}
        file_ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(allowed_extensions)}")
        
        # Extract text from file
        from interview_service.resume_analyzer import _extract_text_from_uploaded_file
        resume_text = await _extract_text_from_uploaded_file(file_content, file_ext)
        
        if not resume_text or len(resume_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Could not extract sufficient text from resume file")
        
        # Parse resume with LLM
        from interview_service.resume_analyzer import analyze_resume_with_llm
        logger.info(f"Parsing resume with LLM (extracted {len(resume_text)} characters)")
        parsed_resume_data = await analyze_resume_with_llm(resume_text)
        
        if not parsed_resume_data or (not parsed_resume_data.skills and not parsed_resume_data.projects):
            logger.warning(f"LLM parsing returned empty data. Skills: {len(parsed_resume_data.skills) if parsed_resume_data else 0}, Projects: {len(parsed_resume_data.projects) if parsed_resume_data else 0}")
        
        # Store only parsed data, not the file itself (to save storage costs)
        # We have all the information we need from the parsed data
        from datetime import datetime, timezone
        import uuid
        
        resume_id = str(uuid.uuid4())
        
        # Create resume metadata with parsed data (no file storage)
        resume_meta = {
            "id": resume_id,
            "name": file.filename,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            # Store parsed data for quick access (this is all we need)
            "parsedData": parsed_resume_data.model_dump(mode='json') if parsed_resume_data else None,
            # Store the extracted text as well (for potential re-parsing if needed)
            "extractedText": resume_text[:10000] if len(resume_text) > 10000 else resume_text  # Store first 10k chars
        }
        
        logger.info(f"Resume parsed and stored (no file storage): {resume_id}, skills: {len(parsed_resume_data.skills) if parsed_resume_data else 0}, projects: {len(parsed_resume_data.projects) if parsed_resume_data else 0}")
        
        # Get current profile
        cache_key = f"user_profile:{user_id}"
        profile = None
        try:
            cached_profile = await redis_client.get(cache_key)
            if cached_profile:
                profile = cached_profile
        except Exception as e:
            logger.debug(f"Redis cache read failed (non-critical): {e}")
        
        if not profile:
            profile = await firestore_client.get_document("users", user_id) or {}
        
        resumes = profile.get("resumes", [])
        resumes.append(resume_meta)
        
        # Update profile with new resume
        logger.info(f"💾 Saving resume metadata to Firestore for user {user_id}")
        logger.debug(f"Resumes list length: {len(resumes)}")
        
        success = await firestore_client.set_document(
            "users", 
            user_id, 
            {"resumes": resumes}, 
            merge=True
        )
        
        if not success:
            logger.error(f"❌ Failed to save resume metadata to Firestore for user {user_id}")
            # Check if Firestore client is initialized
            if not firestore_client.db:
                logger.error("Firestore client is not initialized!")
            raise HTTPException(
                status_code=500, 
                detail="Failed to save resume metadata. Please try again."
            )
        
        logger.info(f"✅ Successfully saved resume metadata for user {user_id}")
        
        # Update Redis cache
        try:
            profile["resumes"] = resumes
            await redis_client.set(cache_key, profile, expire=900)
        except Exception as e:
            logger.debug(f"Redis cache update failed (non-critical): {e}")
        
        return {
            "status": "ok",
            "resume": {
                "id": resume_id,
                "name": file.filename,
                "parsed": True,
                "skills": [s.name for s in parsed_resume_data.skills] if parsed_resume_data else [],
                "projects": [p.name for p in parsed_resume_data.projects] if parsed_resume_data else []
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload resume: {e}")


@app.post("/api/resumes")
async def add_resume_metadata(
    resume_data: Dict[str, Any],
    user: dict = Depends(get_current_user)
):
    """
    Add resume metadata (deprecated - use /api/resumes/upload instead).
    Kept for backward compatibility.
    """
    try:
        user_id = user["uid"]
        
        # Validate required fields
        if "id" not in resume_data or "name" not in resume_data:
            raise HTTPException(status_code=400, detail="Missing required fields: id, name")
        
        # Get current profile (try cache first)
        cache_key = f"user_profile:{user_id}"
        profile = None
        try:
            cached_profile = await redis_client.get(cache_key)
            if cached_profile:
                profile = cached_profile
        except Exception as e:
            logger.debug(f"Redis cache read failed (non-critical): {e}")
        
        if not profile:
            profile = await firestore_client.get_document("users", user_id)
        
        resumes = profile.get("resumes", []) if profile else []
        
        # Add uploaded timestamp if not present
        if "uploadedAt" not in resume_data:
            from datetime import datetime, timezone
            resume_data["uploadedAt"] = datetime.now(timezone.utc).isoformat()
        
        # Add resume to list (avoid duplicates)
        resume_ids = [r.get("id") for r in resumes if r.get("id")]
        if resume_data["id"] not in resume_ids:
            resumes.append(resume_data)
        else:
            # Update existing resume
            for i, r in enumerate(resumes):
                if r.get("id") == resume_data["id"]:
                    resumes[i] = resume_data
                    break
        
        # Update profile with new resumes list
        success = await firestore_client.set_document(
            "users", 
            user_id, 
            {"resumes": resumes}, 
            merge=True
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add resume")
        
        # Update Redis cache
        cache_key = f"user_profile:{user_id}"
        try:
            if profile:
                profile["resumes"] = resumes
                await redis_client.set(cache_key, profile, expire=900)
        except Exception as e:
            logger.debug(f"Redis cache update failed (non-critical): {e}")
        
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding resume: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add resume: {e}")


# ============================================================================
# Interview Endpoints
# ============================================================================
@app.post("/api/interviews/start", response_model=StartInterviewResponse)
async def start_interview_endpoint(
    request: StartInterviewRequest,
    user: dict = Depends(get_current_user)
):
    """Start a new interview session."""
    try:
        # Verify user ID matches
        if request.user_id != user["uid"]:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get resume data (with caching)
        # Try to fetch profile data from cache first for faster resume parsing
        profile_data = None
        cache_key = f"user_profile:{request.user_id}"
        try:
            cached_profile = await redis_client.get(cache_key)
            if cached_profile:
                profile_data = cached_profile
                logger.debug(f"Using cached profile for resume parsing: {request.user_id}")
        except Exception as e:
            logger.debug(f"Redis cache read failed for resume parsing (non-critical): {e}")
        
        # If not in cache, fetch from Firestore
        if not profile_data:
            profile_data = await firestore_client.get_document("users", request.user_id)
            # Cache it for next time (15 minutes)
            if profile_data:
                try:
                    await redis_client.set(cache_key, profile_data, expire=900)
                except Exception as e:
                    logger.debug(f"Redis cache write failed (non-critical): {e}")
        
        # Get resume data - prioritize pre-parsed data (fast, no parsing needed)
        resume_data = None
        if request.resume_id and profile_data:
            # Find resume metadata
            resumes = profile_data.get("resumes", [])
            resume_meta = next((r for r in resumes if str(r.get("id")) == str(request.resume_id)), None)
            
            if resume_meta and resume_meta.get("parsedData"):
                # Use pre-parsed data (fast - no LLM call, no file download)
                try:
                    from interview_service.models import ResumeData
                    resume_data = ResumeData(**resume_meta["parsedData"])
                    logger.info(f"✓ Using pre-parsed resume data for {request.resume_id} (skills: {len(resume_data.skills)}, projects: {len(resume_data.projects)})")
                except Exception as e:
                    logger.warning(f"Error loading pre-parsed resume data: {e}, will parse on the fly")
                    resume_data = None
        
        # If no pre-parsed data, parse on the fly (fallback - should be rare)
        if not resume_data:
            logger.info(f"Parsing resume on the fly for {request.resume_id} (pre-parsed data not available)")
            resume_data = await get_resume_data(
                resume_id=request.resume_id,
                resume_text=None,
                profile_data=profile_data
            )
        
        # If resume_data is empty and we have resume_id, log warning
        if not resume_data.skills and not resume_data.projects and request.resume_id:
            logger.warning(f"No resume data found for resume_id: {request.resume_id}. Using empty resume data.")
        
        # Ensure we have at least some basic data for question generation
        if not resume_data.skills and not resume_data.projects:
            logger.info("No resume data available. Interview will proceed with role-based questions only.")
        
        # Calculate skill weights (now async with LLM extraction)
        skill_weights = await calculate_skill_weights(
            role=request.role,
            resume_data=resume_data,
            use_llm_extraction=True
        )
        
        # Create interview state
        interview_state = await create_interview_state(
            user_id=request.user_id,
            role=request.role,
            resume_data=resume_data,
            skill_weights=skill_weights,
            max_questions=15  # Increased for phased approach
        )
        
        # Store BYOK OpenRouter key in Redis (not Firestore - client-side only, temporary)
        if request.byok_openrouter_key:
            byok_key = f"interview:{interview_state.interview_id}:byok_openrouter"
            try:
                # Check if Redis is connected
                if not redis_client.redis:
                    logger.error(f"❌ Cannot store BYOK key: Redis is not connected. Please start Redis server or set REDIS_URL in .env")
                    logger.error(f"❌ Redis URL configured: {settings.REDIS_URL}")
                    logger.error(f"❌ BYOK OpenRouter key will not be used for this interview")
                else:
                    # Store as plain string (not JSON) so it can be retrieved easily
                    stored = await redis_client.set(byok_key, request.byok_openrouter_key, expire=3600)  # 1 hour TTL
                    if stored:
                        logger.info(f"✅ Stored BYOK OpenRouter key for interview {interview_state.interview_id} (not persisted to DB, key length: {len(request.byok_openrouter_key)})")
                        # Verify it was stored correctly
                        verify_key = await redis_client.get(byok_key)
                        if verify_key:
                            logger.info(f"✅ Verified BYOK key stored in Redis (retrieved length: {len(str(verify_key))})")
                        else:
                            logger.warning(f"⚠️ BYOK key storage verification failed - key not found immediately after storing")
                    else:
                        logger.warning(f"⚠️ Failed to store BYOK key in Redis (set() returned False)")
            except Exception as e:
                logger.warning(f"Failed to store BYOK OpenRouter key in Redis: {e}", exc_info=True)
        
        # Get candidate name safely from profile (if available)
        candidate_name = get_candidate_name_safely(profile_data) if profile_data else None
        
        # Generate first question (phased approach: starts with projects)
        first_question = await select_next_question_phased(
            interview_state,
            last_evaluation=None,
            candidate_name=candidate_name
        )
        
        if not first_question:
            raise HTTPException(status_code=500, detail="Failed to generate first question")
        
        # Update state with first question
        interview_state.current_question = first_question
        interview_state.current_skill = first_question.skill
        # Set current_project if it's a project question
        if interview_state.current_phase == InterviewPhase.PROJECTS and first_question.context and first_question.context.get("project"):
            interview_state.current_project = first_question.context.get("project")
        
        # Save state (Redis is primary, Firestore is optional)
        from interview_service.interview_state import save_interview_state, save_interview_state_to_firestore
        await save_interview_state(interview_state)
        # Firestore save is non-blocking - don't fail if it errors
        try:
            await save_interview_state_to_firestore(interview_state)
        except Exception as e:
            logger.warning(f"Failed to save to Firestore (non-critical): {e}")
        
        await start_interview(interview_state.interview_id)
        
        # Convert skill_weights to response model
        skill_weights_response = [
            SkillWeightResponse(
                skill=sw.skill,
                weight=sw.weight,
                role_relevance=sw.role_relevance
            )
            for sw in skill_weights
        ]
        
        return StartInterviewResponse(
            interview_id=interview_state.interview_id,
            first_question=first_question,
            estimated_duration="30-45 minutes",
            skill_weights=skill_weights_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error starting interview: {e}")
        logger.error(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to start interview: {str(e)}")


@app.post("/api/interviews/{interview_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    interview_id: str,
    answer: Answer,
    user: dict = Depends(get_current_user)
):
    """Submit an answer and get next question."""
    try:
        # Load interview state
        state = await load_interview_state(interview_id)
        if not state:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        # Verify user owns this interview
        if state.user_id != user["uid"]:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Check if interview is completed
        if state.status.value == "completed":
            raise HTTPException(status_code=400, detail="Interview already completed")
        
        # Get current question
        current_question = state.current_question
        if not current_question:
            raise HTTPException(status_code=400, detail="No current question")
        
        # Evaluate answer
        evaluation = await evaluate_answer(
            question=current_question,
            answer=answer,
            previous_evaluations=[
                e.model_dump() for eval_list in state.answered_skills.values()
                for e in eval_list
            ],
            state=state
        )
        
        # Add answer to state (handle project vs skill answers)
        if state.current_project:
            # Project-phase answer
            if state.current_project not in state.answered_projects:
                state.answered_projects[state.current_project] = []
            state.answered_projects[state.current_project].append(evaluation)
            # Also track the main skill from the project
            if current_question.skill:
                if current_question.skill not in state.answered_skills:
                    state.answered_skills[current_question.skill] = []
                state.answered_skills[current_question.skill].append(evaluation)
        else:
            # Skill-phase answer
            if current_question.skill:
                if current_question.skill not in state.answered_skills:
                    state.answered_skills[current_question.skill] = []
                state.answered_skills[current_question.skill].append(evaluation)
        
        # Update phase question count and difficulty
        update_phase_question_count(state)
        state.current_difficulty = evaluation.next_difficulty
        state.total_questions += 1
        state.questions_asked.append(current_question)
        
        # Check if interview should continue (time-based: 30 minutes)
        time_limit_reached = False
        if state.started_at:
            from datetime import datetime
            elapsed = (datetime.utcnow() - state.started_at).total_seconds() / 60  # minutes
            time_limit_reached = elapsed >= state.interview_duration_minutes
        
        if time_limit_reached:
            # Complete interview
            await complete_interview(interview_id)
            
            # Generate report asynchronously (don't block response)
            from interview_service.report_generator import generate_interview_report
            # Get user profile for report
            profile_data = await firestore_client.get_document("users", state.user_id)
            # Generate report in background (don't await - return immediately)
            asyncio.create_task(generate_interview_report(interview_id, state, profile_data))
            
            return AnswerResponse(
                evaluation=evaluation,
                next_question=None,
                progress=calculate_progress(state),
                completed=True
            )
        
        # Get candidate name safely from profile
        profile_data = await firestore_client.get_document("users", state.user_id)
        candidate_name = get_candidate_name_safely(profile_data)
        
        # Select next question using phased approach
        next_question = await select_next_question_phased(
            state,
            last_evaluation=evaluation,
            candidate_name=candidate_name
        )
        
        if next_question:
            # Update state with next question
            state.current_question = next_question
            state.current_skill = next_question.skill
            # Set/clear current_project based on phase and question context
            if state.current_phase == InterviewPhase.PROJECTS and next_question.context and next_question.context.get("project"):
                state.current_project = next_question.context.get("project")
            elif state.current_phase != InterviewPhase.PROJECTS:
                state.current_project = None
        
        # Save updated state
        from interview_service.interview_state import save_interview_state, save_interview_state_to_firestore
        await save_interview_state(state)
        await save_interview_state_to_firestore(state)
        
        # Calculate progress
        progress = calculate_progress(state)
        
        return AnswerResponse(
            evaluation=evaluation,
            next_question=next_question,
            progress=progress,
            completed=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/interviews")
async def get_interviews(user: dict = Depends(get_current_user)):
    """Get all interviews for the user, sorted by most recent."""
    try:
        user_id = user["uid"]
        logger.info(f"📋 GET /api/interviews - Fetching interviews for user: {user_id}")
        
        # Track interview IDs we've seen to avoid duplicates
        seen_interview_ids = set()
        formatted_interviews = []
        
        # 1. Query reports collection (reports contain interview_id)
        reports = await firestore_client.query_collection(
            collection="reports",
            filters=[("user_id", "==", user_id)],
            order_by=None,
            order_direction="DESCENDING",
            limit=100
        )
        
        logger.info(f"📊 Found {len(reports)} reports from Firestore query for user {user_id}")
        
        # If query returned empty, try getting all reports and filtering in Python
        if len(reports) == 0:
            logger.warning(f"⚠️ No reports found with filtered query. Trying alternative approach...")
            all_reports = await firestore_client.query_collection(
                collection="reports",
                filters=None,
                order_by=None,
                order_direction="DESCENDING",
                limit=500
            )
            logger.info(f"📊 Found {len(all_reports)} total reports in collection")
            
            reports = [
                r for r in all_reports 
                if r.get("user_id") == user_id or r.get("userId") == user_id
            ]
            logger.info(f"📊 Filtered to {len(reports)} reports for user {user_id}")
        
        # 2. Also query interviews collection for interviews without reports
        interviews_raw = await firestore_client.query_collection(
            collection="interviews",
            filters=[("user_id", "==", user_id)],
            order_by=None,
            order_direction="DESCENDING",
            limit=100
        )
        
        logger.info(f"📊 Found {len(interviews_raw)} interviews from Firestore for user {user_id}")
        
        # Helper to sort by date
        def get_sort_key(doc):
            created_at = doc.get("created_at") or doc.get("started_at")
            if isinstance(created_at, str):
                return created_at
            elif hasattr(created_at, 'isoformat'):
                return created_at.isoformat()
            return ""
        
        # Helper to convert datetime to string
        from datetime import datetime
        def convert_datetime(val):
            if val is None:
                return None
            if isinstance(val, str):
                return val
            if hasattr(val, 'isoformat'):
                return val.isoformat()
            return str(val)
        
        # 3. Process reports first (they have complete info)
        for report_doc in reports:
            interview_id = report_doc.get("interview_id")
            if interview_id and interview_id in seen_interview_ids:
                continue
            if interview_id:
                seen_interview_ids.add(interview_id)
            
            report_data = report_doc.get("report_data", {})
            
            # Try to get interview state for additional info
            interview_state = None
            if interview_id:
                try:
                    interview_state = await load_interview_state(interview_id)
                except Exception as e:
                    logger.debug(f"Could not load interview state for {interview_id}: {e}")
            
            interview = {
                "interview_id": interview_id,
                "report_id": report_doc.get("report_id"),
                "role": report_doc.get("role", report_data.get("role", "Unknown")),
                "status": interview_state.status.value if interview_state else "completed",
                "overall_score": report_doc.get("overall_score", report_data.get("overall_score", 0)),
                "created_at": convert_datetime(report_doc.get("created_at")),
                "total_questions": report_data.get("total_questions", 0),
                "recommendation": report_data.get("recommendation", "maybe"),
                "started_at": convert_datetime(interview_state.started_at) if interview_state else None,
                "completed_at": convert_datetime(interview_state.completed_at) if interview_state else convert_datetime(report_doc.get("created_at"))
            }
            
            formatted_interviews.append(interview)
        
        # 4. Also process interviews without reports (in-progress or report generation failed)
        for interview_doc in interviews_raw:
            interview_id = interview_doc.get("interview_id")
            if interview_id and interview_id in seen_interview_ids:
                continue  # Already have this from reports
            if interview_id:
                seen_interview_ids.add(interview_id)
            
            # Try to load interview state for more info
            interview_state = None
            try:
                interview_state = await load_interview_state(interview_id)
            except Exception as e:
                logger.debug(f"Could not load interview state for {interview_id}: {e}")
            
            interview = {
                "interview_id": interview_id,
                "report_id": interview_doc.get("report_id"),
                "role": interview_doc.get("role", interview_state.role.value if interview_state else "Unknown"),
                "status": interview_state.status.value if interview_state else interview_doc.get("status", "in_progress"),
                "overall_score": interview_doc.get("overall_score", 0),
                "created_at": convert_datetime(interview_doc.get("created_at") or interview_doc.get("started_at")),
                "total_questions": interview_state.total_questions if interview_state else interview_doc.get("total_questions", 0),
                "recommendation": interview_doc.get("recommendation"),
                "started_at": convert_datetime(interview_state.started_at if interview_state else interview_doc.get("started_at")),
                "completed_at": convert_datetime(interview_state.completed_at if interview_state else interview_doc.get("completed_at"))
            }
            
            formatted_interviews.append(interview)
        
        # 5. Sort by created_at descending
        formatted_interviews.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        
        logger.info(f"✅ Returning {len(formatted_interviews)} formatted interviews (from {len(reports)} reports + {len(interviews_raw)} interviews)")
        return formatted_interviews
        
    except HTTPException:
        raise
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error getting interviews: {e}", exc_info=True)
        # Return proper JSON error response
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred while fetching interviews: {sanitize_error_message(e)}"
        )


@app.delete("/api/admin/interviews/user/{user_id}")
async def delete_user_interviews_admin(
    user_id: str,
    user: dict = Depends(get_current_user),
    confirm: bool = Query(False, description="Set to true to actually delete (safety measure)")
):
    """
    Delete all interviews and reports for a specific user.
    Requires admin privileges or user deleting their own data.
    
    Query params:
        - confirm: Must be true to actually delete (safety measure)
    """
    try:
        current_user_id = user["uid"]
        
        # Allow if user is deleting their own data, or if they're an admin
        # For now, we'll allow users to delete their own data
        if user_id != current_user_id:
            # TODO: Add admin check here if you have admin roles
            raise HTTPException(status_code=403, detail="You can only delete your own interviews")
        
        if not confirm:
            # Query first to show what would be deleted
            interviews = await firestore_client.query_collection(
                collection="interviews",
                filters=[("user_id", "==", user_id)]
            )
            reports = await firestore_client.query_collection(
                collection="reports",
                filters=[("user_id", "==", user_id)]
            )
            
            return {
                "preview": True,
                "interviews_count": len(interviews),
                "reports_count": len(reports),
                "message": "Set confirm=true to actually delete. This is a preview.",
                "interview_ids": [doc.get("id") or doc.get("interview_id") for doc in interviews],
                "report_ids": [doc.get("id") or doc.get("report_id") for doc in reports]
            }
        
        # Actually delete
        interview_ids = []
        interviews = await firestore_client.query_collection(
            collection="interviews",
            filters=[("user_id", "==", user_id)]
        )
        for interview in interviews:
            interview_id = interview.get("id") or interview.get("interview_id")
            if interview_id:
                interview_ids.append(interview_id)
        
        report_ids = []
        reports = await firestore_client.query_collection(
            collection="reports",
            filters=[("user_id", "==", user_id)]
        )
        for report in reports:
            report_id = report.get("id") or report.get("report_id")
            if report_id:
                report_ids.append(report_id)
        
        # Delete interviews
        deleted_interviews = []
        for interview_id in interview_ids:
            success = await firestore_client.delete_document("interviews", interview_id)
            if success:
                deleted_interviews.append(interview_id)
        
        # Delete reports
        deleted_reports = []
        for report_id in report_ids:
            success = await firestore_client.delete_document("reports", report_id)
            if success:
                deleted_reports.append(report_id)
        
        logger.info(f"🗑️  Deleted {len(deleted_interviews)} interviews and {len(deleted_reports)} reports for user {user_id}")
        
        return {
            "success": True,
            "deleted_interviews": len(deleted_interviews),
            "deleted_reports": len(deleted_reports),
            "interview_ids": deleted_interviews,
            "report_ids": deleted_reports
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user interviews: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete interviews: {str(e)}")


@app.post("/api/admin/regenerate-report/{interview_id}")
async def regenerate_report_endpoint(
    interview_id: str,
    user: dict = Depends(get_current_user)
):
    """Manually regenerate report for a specific interview (admin endpoint)."""
    try:
        from interview_service.interview_state import load_interview_state
        from interview_service.report_generator import generate_interview_report
        from shared.db.firestore_client import firestore_client
        
        logger.info(f"🔄 Manual report regeneration requested for interview: {interview_id}")
        
        # Load interview state
        state = await load_interview_state(interview_id)
        if not state:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        # Get user profile
        profile_data = await firestore_client.get_document("users", state.user_id)
        
        # Generate report
        report_data = await generate_interview_report(interview_id, state, profile_data)
        
        if report_data:
            logger.info(f"✅ Report regenerated successfully for interview: {interview_id}")
            return {
                "status": "success",
                "message": "Report regenerated successfully",
                "report_id": state.report_id,
                "interview_id": interview_id
            }
        else:
            raise HTTPException(status_code=500, detail="Report generation failed")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to regenerate report: {e}")


@app.post("/api/admin/push-sample-report")
async def push_sample_report_endpoint(
    user: dict = Depends(get_current_user)
):
    """Push sample report data to Firebase (admin endpoint for testing)."""
    try:
        # Use the authenticated user's ID, or hardcode for specific user
        user_id = "8iwqHcixnOWIvND1FxNHH24syIR2"  # Hardcoded for initial testing
        
        # Import report generator
        from interview_service.report_generator import generate_interview_report
        from datetime import datetime, timezone
        import uuid
        
        # Create a minimal interview state for report generation
        from interview_service.models import InterviewState, InterviewStatus, InterviewPhase, DifficultyLevel, InterviewRole, InterviewFlowState, ResumeData
        
        # Sample report data structure
        report_id = str(uuid.uuid4())
        interview_id = str(uuid.uuid4())
        
        report_data = {
            "overall_score": 85,
            "section_scores": {
                "technical": 88,
                "communication": 82,
                "problem_solving": 85
            },
            "strengths": [
                "Strong understanding of core programming concepts",
                "Clear communication and articulation of technical ideas",
                "Good problem-solving approach with logical thinking",
                "Demonstrated ability to explain complex topics simply"
            ],
            "weaknesses": [
                "Could improve time management during complex problems",
                "Some gaps in advanced system design concepts",
                "Could benefit from more practice with optimization techniques"
            ],
            "detailed_feedback": "The candidate demonstrated solid technical knowledge and communication skills throughout the interview. They showed a good understanding of fundamental concepts and were able to articulate their thought process clearly. While there are areas for improvement in advanced topics, the overall performance indicates strong potential.",
            "recommendation": "maybe",
            "improvement_suggestions": [
                "Practice more system design problems to strengthen architecture knowledge",
                "Work on time management strategies for technical interviews",
                "Review advanced algorithms and data structures",
                "Continue building projects to gain practical experience"
            ],
            "skill_scores": {
                "Python": 0.9,
                "JavaScript": 0.85,
                "React": 0.88,
                "Node.js": 0.82,
                "Database Design": 0.80,
                "System Design": 0.75
            },
            "questions": [
                "Can you tell me about yourself and your background?",
                "Explain how you would design a scalable web application",
                "Describe a challenging project you worked on recently",
                "How would you optimize a slow database query?",
                "Implement a function to reverse a linked list"
            ],
            "answers": [
                "I'm a full-stack developer with 3 years of experience working with Python and JavaScript. I've built several web applications using React and Node.js, and I'm passionate about creating efficient and scalable solutions.",
                "I would start by identifying the core requirements and constraints. Then I'd design a microservices architecture with load balancing, caching layers using Redis, and a CDN for static assets. I'd also implement database sharding for horizontal scaling.",
                "I recently worked on an e-commerce platform where I had to optimize the checkout process. I implemented caching strategies and database indexing which reduced response time by 60%.",
                "I would first analyze the query execution plan, then add appropriate indexes, consider query rewriting, and potentially denormalize some data if needed. I'd also look at connection pooling and caching strategies.",
                "I would use a two-pointer approach or iterative method to reverse the linked list. Let me explain the algorithm step by step..."
            ],
            "role": "fullstack-developer",
            "total_questions": 5,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        report_doc = {
            "report_id": report_id,
            "interview_id": interview_id,
            "user_id": user_id,
            "role": "fullstack-developer",
            "report_data": report_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "overall_score": 85
        }
        
        # Store in Firestore
        success = await firestore_client.set_document(
            "reports",
            report_id,
            report_doc
        )
        
        if success:
            logger.info(f"✅ Sample report pushed for user {user_id}: {report_id}")
            return {
                "status": "success",
                "message": "Sample report pushed successfully",
                "report_id": report_id,
                "interview_id": interview_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to push report to Firestore")
            
    except Exception as e:
        logger.error(f"Error pushing sample report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to push sample report: {e}")


@app.get("/api/interviews/{interview_id}/report")
async def get_interview_report(
    interview_id: str,
    user: dict = Depends(get_current_user)
):
    """Get interview report by interview_id."""
    try:
        # Verify interview exists and user owns it
        state = await load_interview_state(interview_id)
        if not state:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        if state.user_id != user["uid"]:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get report from Firestore
        report_id = state.report_id if hasattr(state, 'report_id') and state.report_id else None
        
        if not report_id:
            # Try to find report by interview_id
            reports = await firestore_client.query_collection(
                collection="reports",
                filters=[("interview_id", "==", interview_id)],
                limit=1
            )
            if reports:
                report_doc = reports[0]
                report_data = report_doc.get("report_data", {})
                return {
                    "status": "ok",
                    "report": report_data
                }
            else:
                # Report doesn't exist - try to generate it now if interview is completed
                if state.status.value == "completed":
                    logger.info(f"📊 No report found for completed interview {interview_id}, generating now...")
                    try:
                        from interview_service.report_generator import generate_interview_report
                        profile_data = await firestore_client.get_document("users", state.user_id)
                        
                        # Generate report synchronously (blocking) since user is waiting
                        report_data = await generate_interview_report(interview_id, state, profile_data)
                        
                        if report_data:
                            logger.info(f"✅ Report generated successfully for {interview_id}")
                            return {
                                "status": "ok",
                                "report": report_data
                            }
                        else:
                            logger.error(f"❌ Report generation returned None for {interview_id}")
                            raise HTTPException(
                                status_code=500,
                                detail="Failed to generate report. Please try again."
                            )
                    except HTTPException:
                        raise
                    except Exception as e:
                        logger.error(f"❌ Error generating report: {e}", exc_info=True)
                        raise HTTPException(
                            status_code=500,
                            detail=f"Error generating report: {str(e)}"
                        )
                else:
                    # Interview not completed yet - generate partial report anyway
                    logger.info(f"📊 Generating partial report for in-progress interview {interview_id}")
                    try:
                        from interview_service.report_generator import generate_interview_report
                        profile_data = await firestore_client.get_document("users", state.user_id)
                        
                        # Generate partial report
                        report_data = await generate_interview_report(interview_id, state, profile_data)
                        
                        if report_data:
                            # Mark it as partial
                            report_data["is_partial"] = True
                            report_data["status_message"] = "This is a partial report. Interview was not completed."
                            logger.info(f"✅ Partial report generated for {interview_id}")
                            return {
                                "status": "ok",
                                "report": report_data
                            }
                        else:
                            raise HTTPException(
                                status_code=500,
                                detail="Failed to generate report. Please try again."
                            )
                    except HTTPException:
                        raise
                    except Exception as e:
                        logger.error(f"Error generating partial report: {e}", exc_info=True)
                        raise HTTPException(
                            status_code=500,
                            detail=f"Error generating report: {str(e)}"
                        )
        
        # Get report by report_id
        report_doc = await firestore_client.get_document("reports", report_id)
        if not report_doc:
            raise HTTPException(status_code=404, detail="Report not found")
        
        report_data = report_doc.get("report_data", {})
        return {
            "status": "ok",
            "report": report_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch report: {e}")


@app.get("/api/interviews/{interview_id}")
async def get_interview_status(
    interview_id: str,
    user: dict = Depends(get_current_user)
):
    """Get interview status and progress."""
    try:
        state = await load_interview_state(interview_id)
        if not state:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        # Verify user owns this interview
        if state.user_id != user["uid"]:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        return {
            "interview_id": interview_id,
            "status": state.status.value,
            "progress": calculate_progress(state),
            "current_question": state.current_question.model_dump() if state.current_question else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting interview status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interviews/{interview_id}/end")
async def end_interview_endpoint(
    interview_id: str,
    user: dict = Depends(get_current_user)
):
    """Manually end an interview (user clicked End Call button)."""
    try:
        state = await load_interview_state(interview_id)
        if not state:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        # Verify user owns this interview
        if state.user_id != user["uid"]:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Check if already completed
        if state.status.value == "completed":
            return {
                "status": "ok",
                "message": "Interview was already completed",
                "interview_id": interview_id
            }
        
        # Mark interview as completed
        logger.info(f"🛑 User manually ended interview: {interview_id}")
        await complete_interview(interview_id)
        
        # Generate report in background
        try:
            from interview_service.report_generator import generate_interview_report
            profile_data = await firestore_client.get_document("users", state.user_id)
            
            async def _generate_report():
                try:
                    result = await generate_interview_report(interview_id, state, profile_data)
                    if result:
                        logger.info(f"✅ Report generated for manually ended interview: {interview_id}")
                    else:
                        logger.error(f"❌ Report generation failed for: {interview_id}")
                except Exception as e:
                    logger.error(f"❌ Report generation error for {interview_id}: {e}", exc_info=True)
            
            asyncio.create_task(_generate_report())
        except Exception as e:
            logger.error(f"Error starting report generation: {e}")
        
        # Close WebSocket if connected
        if interview_id in manager.active_connections:
            try:
                websocket_handler._stop_keepalive(interview_id)
                manager.disconnect(interview_id)
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
        
        return {
            "status": "ok",
            "message": "Interview ended successfully",
            "interview_id": interview_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending interview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/interview/{interview_id}")
async def websocket_endpoint(websocket: WebSocket, interview_id: str):
    """WebSocket endpoint for real-time interview communication."""
    import traceback
    logger.info(f"[WS] ⚠️ NEW INCOMING WebSocket connection attempt for interview: {interview_id}")
    logger.info(f"[WS] Connection attempt stack trace:\n{traceback.format_stack()}")
    
    try:
        # STEP 1: Check for existing connection BEFORE accepting new one
        # CRITICAL FIX: Reject duplicate connections instead of replacing them
        if interview_id in manager.active_connections:
            existing_ws = manager.active_connections[interview_id]
            # Check if existing connection is still alive
            try:
                # Try to check if connection is still open (non-blocking check)
                # If we can't determine, assume it's still active
                logger.warning(f"[WS] ⚠️ DUPLICATE WebSocket connection attempt for {interview_id} - REJECTING new connection to prevent audio stream interruption")
                logger.warning(f"[WS] Existing connection state: {existing_ws.client_state if hasattr(existing_ws, 'client_state') else 'unknown'}")
                
                # Reject the new connection with clear reason
                await websocket.close(code=1008, reason="Duplicate connection rejected - existing connection is active")
                logger.info(f"[WS] Rejected duplicate WebSocket connection for {interview_id} (code=1008)")
                return  # Exit early - don't process this connection
            except Exception as e:
                # If we can't check existing connection, it might be dead - allow replacement
                logger.warning(f"[WS] Could not verify existing connection state for {interview_id}: {e} - allowing replacement")
                # Continue to replace (old behavior as fallback)
                old_connection = existing_ws
                del manager.active_connections[interview_id]
                logger.info(f"[WS] Removed potentially dead connection from manager for interview: {interview_id}")
        else:
            old_connection = None
            logger.info(f"[WS] ✓ New WebSocket connection created for {interview_id} (no existing connection)")
        
        # STEP 2: Accept new WebSocket connection (required by FastAPI)
        await websocket.accept()
        logger.info(f"[WS] WebSocket connection accepted for interview: {interview_id}")
        
        # STEP 3: Add new connection to manager
        manager.active_connections[interview_id] = websocket
        # Mark WebSocket as active in handler
        websocket_handler.mark_websocket_connected(interview_id)
        logger.info(f"[WS] ✓ New WebSocket added to manager for interview: {interview_id} (Total: {len(manager.active_connections)})")
        
        # STEP 4: Close old connection if it exists (only if we're replacing)
        if old_connection and old_connection != websocket:
            # Close old connection in background (don't block)
            # Use code 1001 with clear reason so frontend knows not to reconnect
            try:
                await old_connection.close(code=1001, reason="Connection replaced")
                logger.info(f"[WS] Closed old WebSocket connection for interview: {interview_id} (code=1001)")
            except (RuntimeError, Exception) as e:
                # Connection might already be closed - this is expected
                logger.debug(f"[WS] Old connection already closed or error closing (expected): {e}")
        
        # Don't clear sent_question_ids - we want to remember which question was sent
        
        # Send welcome message first
        try:
            await manager.send_message(interview_id, {
                "type": "connected",
                "message": "WebSocket connected successfully",
                "interview_id": interview_id
            })
            logger.info(f"Welcome message sent for interview: {interview_id}")
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
            # Don't raise - connection might still be valid
        
        # Verify interview exists and send current question if available
        try:
            state = await load_interview_state(interview_id)
            if not state:
                logger.warning(f"Interview {interview_id} not found in Redis/Firestore, but allowing connection")
                # Don't close - the interview might be created shortly
                # Send a warning message (but connection is already established)
                await manager.send_message(interview_id, {
                    "type": "error",
                    "message": "Interview not found. Please ensure the interview has been started."
                })
                # Still allow connection - interview might be created soon
            elif state.status.value == "completed":
                # Interview is already completed - close WebSocket and tell frontend to go to report
                logger.info(f"Interview {interview_id} is already completed - redirecting to report")
                await manager.send_message(interview_id, {
                    "type": "completed",
                    "message": "Interview already completed. Redirecting to report..."
                })
                manager.disconnect(interview_id)
                await websocket.close(code=1000, reason="Interview already completed")
                return
            else:
                logger.info(f"Interview {interview_id} found and ready")
                
                # Send current question only if it's different from the last one we sent
                # This prevents duplicate questions on reconnect
                if state.status.value == "in_progress" and state.current_question:
                    current_question_id = state.current_question.question_id
                    last_sent_question_id = manager.get_last_sent_question_id(interview_id)
                    
                    # Only send if this is a new question (different question_id)
                    if current_question_id != last_sent_question_id:
                        logger.info(f"Sending current question {current_question_id} for interview {interview_id}")
                        
                        # Send current question
                        await manager.send_message(interview_id, {
                            "type": "question",
                            "question": state.current_question.model_dump()
                        })
                        
                        # Mark this specific question as sent
                        manager.mark_question_sent(interview_id, current_question_id)
                        
                        # Generate and send TTS audio for current question
                        try:
                            from shared.providers.deepgram_client import deepgram_client
                            import base64
                            
                            # Use tts_text from context if available (for coding questions)
                            question_context = state.current_question.context or {}
                            tts_text = question_context.get("tts_text") if isinstance(question_context, dict) else None
                            audio_text = tts_text if tts_text else state.current_question.question
                            
                            logger.info(f"🎵 TTS: {'Using tts_summary' if tts_text else 'Using full question'} - {audio_text[:50]}...")
                            
                            audio_bytes = await deepgram_client.synthesize_speech(
                                text=audio_text,
                                model="aura-asteria-en",
                                voice="asteria"
                            )
                            
                            if audio_bytes:
                                logger.info(f"✓ TTS generated successfully, size: {len(audio_bytes)} bytes")
                                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                                await manager.send_message(interview_id, {
                                    "type": "audio",
                                    "audio": audio_base64,
                                    "format": "mp3"
                                })
                                logger.info(f"✓ TTS audio sent to frontend")
                            else:
                                logger.warning("⚠️ TTS returned empty audio bytes")
                        except Exception as e:
                            logger.error(f"❌ Error generating TTS for current question: {e}", exc_info=True)
                            # Non-critical, continue without audio
                    else:
                        logger.info(f"Question {current_question_id} already sent for interview {interview_id}, skipping duplicate")
                
                # Send interview state/resume info
                await manager.send_message(interview_id, {
                    "type": "resume",
                    "interview_state": {
                        "status": state.status.value,
                        "current_phase": state.current_phase.value,
                        "total_questions": state.total_questions,
                        "max_questions": state.max_questions,
                        "progress": calculate_progress(state),
                        "flow_state": state.flow_state.value  # Send current flow state
                    }
                })
                
                # If interview is in progress and flow_state is USER_SPEAKING (no current question or no audio), 
                # send flow_state to trigger recording start on frontend
                # This handles the case where interview resumes without audio playing
                if (state.status.value == "in_progress" and 
                    state.flow_state == InterviewFlowState.USER_SPEAKING and
                    not state.current_question):  # No current question means user should speak
                    await manager.send_message(interview_id, {
                        "type": "flow_state",
                        "state": state.flow_state.value
                    })
        except Exception as e:
            logger.error(f"Error loading interview state: {e}")
            # Don't close connection - allow it to proceed
            # The interview might be created after connection
            # Use manager.send_message which handles closed connections gracefully
            await manager.send_message(interview_id, {
                "type": "error",
                "message": f"Error loading interview: {str(e)}"
            })
        
        # CRITICAL: Start WebSocket PING frame task (protocol-level, not JSON message)
        # Uvicorn expects actual WebSocket PING frames to keep the connection alive
        # JSON "ping" messages don't count for Uvicorn's ping timeout
        async def websocket_ping_task():
            """Send periodic WebSocket PING frames (protocol-level) to keep connection alive."""
            try:
                logger.info(f"[WS Ping] Starting protocol-level PING task for {interview_id}")
                while True:
                    await asyncio.sleep(20)  # Send PING frame every 20 seconds (matches Uvicorn's ping_interval)
                    
                    # Check if connection is still active
                    if interview_id not in manager.active_connections:
                        logger.debug(f"[WS Ping] Connection no longer in manager for {interview_id}, stopping ping task")
                        break
                    if manager.active_connections.get(interview_id) != websocket:
                        logger.debug(f"[WS Ping] Connection replaced for {interview_id}, stopping ping task")
                        break
                    
                    try:
                        # CRITICAL: Send actual WebSocket PING frame (protocol-level)
                        # This is different from JSON {"type": "ping"} - Uvicorn needs protocol PING frames
                        # FastAPI/Starlette WebSocket has a ping() method for this
                        await websocket.send_text("")  # Empty text frame as keepalive
                        # Note: FastAPI WebSocket doesn't expose ping() directly, but we can use send_text("")
                        # However, the real fix is the Uvicorn ping_timeout configuration above
                        logger.debug(f"[WS Ping] ✓ Sent keepalive frame for {interview_id}")
                    except Exception as e:
                        # Connection might be closed - exit ping task
                        logger.debug(f"[WS Ping] Keepalive frame failed for {interview_id}: {e} (connection may be closed)")
                        break
            except asyncio.CancelledError:
                logger.info(f"[WS Ping] Ping task CANCELLED for {interview_id}")
            except Exception as e:
                logger.error(f"[WS Ping] Ping task ERROR for {interview_id}: {e}", exc_info=True)
        
        # Start ping task in background
        ping_task = None
        try:
            ping_task = asyncio.create_task(websocket_ping_task())
            logger.debug(f"✓ Started WebSocket ping task for {interview_id}")
        except Exception as e:
            logger.warning(f"Could not start WebSocket ping task for {interview_id}: {e}")
        
        # Initialize last ping time
        manager.last_ping_time[interview_id] = time.time()
        
        # Main message loop - keep connection open
        try:
            while True:
                # Check if this connection is still the active one for this interview
                # If a new connection replaced this one, exit gracefully
                if interview_id not in manager.active_connections:
                    # CRITICAL: This could mean:
                    # 1. A new connection replaced this one (legitimate)
                    # 2. send_message() called disconnect() due to error (shouldn't happen anymore)
                    # 3. Connection was manually removed (shouldn't happen)
                    # Log with more context to diagnose
                    logger.warning(f"[WS Receive Loop] Connection for {interview_id} no longer in manager - exiting receive loop")
                    logger.warning(f"[WS Receive Loop] This might indicate the connection was removed unexpectedly. Check for errors above.")
                    break
                
                if manager.active_connections.get(interview_id) != websocket:
                    # A different WebSocket instance is now in the manager - this means a new connection replaced this one
                    logger.info(f"[WS Receive Loop] Connection for {interview_id} was replaced by new connection, exiting receive loop")
                    break
                
                # Only check ping for connections that are still in active_connections
                if interview_id in manager.active_connections:
                    last_ping = manager.last_ping_time.get(interview_id, time.time())
                    time_since_ping = time.time() - last_ping
                    
                    # Log warning only every 30 seconds (not every loop) if no ping in 120 seconds
                    if time_since_ping > 120 and int(time_since_ping) % 30 == 0:
                        logger.warning(f"⚠️ [Keepalive] No ping received for {interview_id} in {time_since_ping:.1f}s - connection may timeout soon")
                
                # Receive message from client with timeout to prevent FastAPI from closing
                # Use a longer timeout (120 seconds) to allow for ping messages and long pauses
                # CRITICAL: Uvicorn has its own ping timeout (configured to 120s), but we need to keep receiving
                try:
                    # FastAPI's receive_json() has a default timeout
                    # We'll use asyncio.wait_for to extend it to match Uvicorn's ping_timeout
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=120.0)
                    # Update last ping time on ANY message (ping, audio_chunk, etc.) to prevent timeout
                    manager.last_ping_time[interview_id] = time.time()
                except asyncio.TimeoutError:
                    # Timeout waiting for message - check if we should close or continue
                    last_ping = manager.last_ping_time.get(interview_id, time.time())
                    time_since_ping = time.time() - last_ping
                    
                    # CRITICAL: Don't close the connection ourselves - Uvicorn will handle it
                    # If Uvicorn's ping_timeout is 120s, and we haven't received a message in 120s,
                    # Uvicorn will close it. But we should continue trying to receive until that happens.
                    if time_since_ping > 180:  # No ping/message for 3 minutes (longer than Uvicorn timeout)
                        logger.warning(f"⚠️ [Keepalive Timeout] No message received for {interview_id} in {time_since_ping:.1f}s - Uvicorn will close connection")
                        # Don't close manually - let Uvicorn handle it
                        break
                    else:
                        # Continue waiting - timeout is just for this receive call
                        logger.debug(f"⏱️ [Timeout] Receive timeout for {interview_id}, but last ping was {time_since_ping:.1f}s ago - continuing")
                        continue
                except WebSocketDisconnect as e:
                    # Client disconnected normally - this is expected
                    disconnect_code = e.code if hasattr(e, 'code') else 1000
                    disconnect_reason = getattr(e, 'reason', 'Client disconnected')
                    logger.info(f"WebSocket client disconnected: {interview_id}, code: {disconnect_code}, reason: {disconnect_reason}")
                    # Mark as disconnected and stop Deepgram session
                    websocket_handler.mark_websocket_disconnected(interview_id)
                    break
                except Exception as e:
                    # Check if this is a WebSocket disconnect/connection error
                    error_type = type(e).__name__
                    error_msg = str(e)
                    
                    # Check for connection-related errors (these are expected when connection is closed)
                    if "Disconnect" in error_type or "ConnectionClosed" in error_type:
                        # Connection was closed - this is expected (might be replaced by new connection)
                        logger.info(f"WebSocket connection closed: {interview_id}, error: {error_type}")
                        # Mark as disconnected and stop Deepgram session
                        websocket_handler.mark_websocket_disconnected(interview_id)
                        break
                    
                    # Check if connection was closed or not accepted
                    # This can happen when connection is replaced or closed while receiving
                    if "Need to call \"accept\" first" in error_msg:
                        # Connection was replaced or closed - check if we're still the active connection
                        # This is expected when a new connection replaces this one
                        if interview_id not in manager.active_connections or manager.active_connections.get(interview_id) != websocket:
                            # Connection was replaced - this is expected, exit gracefully
                            logger.debug(f"Connection for {interview_id} was replaced, exiting receive loop (expected)")
                        else:
                            # Connection is still active but receiving failed - this is unexpected
                            # Log as debug since it might be a transient FastAPI state issue
                            logger.debug(f"WebSocket receive error (connection might be closing): {interview_id}, {error_msg}")
                        break
                    elif "close message has been sent" in error_msg or "Connection closed" in error_msg:
                        # Connection was closed (possibly by us when replacing it) - this is expected
                        logger.debug(f"WebSocket connection closed while receiving: {interview_id} (expected if connection was replaced)")
                        break
                    
                    # For other errors, check if it's a connection issue
                    if "not connected" in error_msg.lower() or "connection" in error_msg.lower():
                        # Connection error - break the loop
                        logger.info(f"WebSocket connection error: {interview_id}, {error_msg}")
                        break
                    else:
                        # Non-connection error - log and break (connection is likely broken)
                        logger.warning(f"Error receiving WebSocket message: {interview_id}, {error_type}: {error_msg}")
                        break
                
                if not data:
                    logger.warning(f"Received empty message from {interview_id}")
                    continue
                    
                message_type = data.get("type")
                
                if message_type == "ping":
                    # CRITICAL: Update last ping time to prevent FastAPI timeout
                    manager.last_ping_time[interview_id] = time.time()
                    logger.debug(f"💓 [Ping] Received ping from frontend for {interview_id} - updating last_ping_time")
                    
                    # Frontend heartbeat - send keepalive to Deepgram to prevent timeout
                    # This handles cases where audio chunks stall for 1-3 seconds during long continuous speech
                    try:
                        if websocket_handler._live_session_active.get(interview_id, False):
                            # Send a small silence chunk to Deepgram as keepalive
                            silence_chunk = b'\x00' * 1600  # 50ms of silence at 16kHz
                            success = await deepgram_client.send_audio_chunk(interview_id, silence_chunk)
                            if success:
                                logger.debug(f"💓 Heartbeat keepalive sent to Deepgram for {interview_id}")
                                # Update last audio time so keepalive loop knows we're active
                                websocket_handler._last_audio_time[interview_id] = time.time()
                            else:
                                logger.debug(f"💓 Heartbeat keepalive failed for {interview_id} (session may be closing)")
                    except Exception as e:
                        logger.debug(f"💓 Heartbeat error for {interview_id}: {e} (non-critical)")
                    # Respond with pong to keep WebSocket connection alive
                    try:
                        await manager.send_message(interview_id, {"type": "pong"})
                    except Exception:
                        pass  # Non-critical if send fails
                    continue
                
                if message_type == "audio_chunk":
                    # Handle audio chunk for STT
                    # CRITICAL: Wrap in try-except to catch any exceptions that might stop audio forwarding
                    try:
                        audio_data = data.get("data", {})
                        # Log audio chunks at DEBUG level to reduce spam
                        chunk_size = len(audio_data.get("chunk", "")) if audio_data.get("chunk") else 0
                        logger.debug(f"[WS] 📥 Received audio_chunk: {chunk_size} bytes")
                        transcript_result = await websocket_handler.handle_audio_chunk(
                            interview_id,
                            audio_data
                        )
                        logger.debug(f"[WS] ✓ Processed audio_chunk for {interview_id} (timestamp: {time.time():.3f})")
                    except Exception as audio_exception:
                        # CRITICAL: Log any exception during audio processing - this might be silently killing the flow
                        logger.error(f"[WS] ✗✗✗ EXCEPTION processing audio_chunk for {interview_id}: {audio_exception}", exc_info=True)
                        logger.error(f"[WS] This exception may have stopped audio forwarding! Check stack trace above.")
                        # Don't break the loop - continue processing other messages
                        # But log it so we can see if this is the cause
                        
                        # Note: With Deepgram Live API, transcripts come via async callbacks, not return values
                        # handle_audio_chunk returns None for Live API (transcripts are accumulated via callback)
                        # So we don't expect transcript_result here - transcripts are sent via WebSocket from callback
                        if transcript_result:
                            logger.debug(f"✓ Transcript result received synchronously for {interview_id} (using prerecorded API fallback)")
                            # Send accumulated transcript (what user has said so far)
                            accumulated_text = transcript_result.get("accumulated_text", transcript_result.get("text", ""))
                            logger.debug(f"📝 Sending transcript for {interview_id}: {accumulated_text[:50]}...")
                            await manager.send_message(interview_id, {
                                "type": "transcript",
                                "text": accumulated_text,  # Send accumulated transcript, not just chunk
                                "is_final": transcript_result.get("is_final", True),
                                "confidence": transcript_result.get("confidence", 1.0)
                            })
                        # else: For Live API, transcripts come via callback - this is expected, no warning needed
                    except Exception as e:
                        logger.error(f"Error processing audio chunk: {e}")
                        # Don't break connection, just log error
                        # Continue processing other messages
                
                elif message_type == "stop_recording":
                    # User manually stopped recording - get accumulated transcript and submit as answer
                    # CRITICAL: Wrap entire handler in try-except to prevent WebSocket from closing on errors
                    try:
                        logger.info(f"🛑 Stop recording requested for {interview_id}")
                        
                        # Check if interview is already completed - if so, just stop everything and skip processing
                        state = await load_interview_state(interview_id)
                        interview_completed = state and (state.status == InterviewStatus.COMPLETED or 
                                                        state.flow_state == InterviewFlowState.INTERVIEW_COMPLETE)
                        
                        if interview_completed:
                            logger.info(f"⚠️ Interview {interview_id} is already completed, stopping all sessions")
                            websocket_handler._stop_keepalive(interview_id)
                            websocket_handler._live_session_active[interview_id] = False
                            await websocket_handler.stop_live_session(interview_id)
                            # Send message to frontend that interview is completed
                            await manager.send_message(interview_id, {
                                "type": "error",
                                "message": "Interview already completed. No further processing."
                            })
                        else:
                            # CRITICAL: Keep WebSocket active - don't mark as disconnected
                            # Only stop Deepgram session, not the WebSocket connection
                            logger.info(f"[Stop Recording] Processing stop_recording for {interview_id} - keeping WebSocket connected")
                            
                            # Before stopping, send a final keepalive to prevent Deepgram timeout
                            # This gives Deepgram a signal that we're intentionally stopping
                            logger.info(f"[Stop Recording] Sending final keepalive before stopping Deepgram session for {interview_id}")
                            try:
                                # Send a small silence chunk to keep connection alive while we finish
                                silence_chunk = b'\x00' * 1600  # 50ms of silence
                                await deepgram_client.send_audio_chunk(interview_id, silence_chunk)
                                logger.debug(f"[Stop Recording] Sent final keepalive chunk for {interview_id}")
                                # Update last audio time so keepalive knows we just sent data
                                websocket_handler._last_audio_time[interview_id] = time.time()
                            except Exception as e:
                                logger.warning(f"[Stop Recording] Could not send final keepalive: {e} (non-critical, continuing)")
                            
                            # Wait a moment for Deepgram to process any final audio and transcripts
                            # Keep keepalive running during this time to prevent timeout
                            logger.debug(f"[Stop Recording] Waiting for Deepgram to finish processing...")
                            await asyncio.sleep(1.0)  # Give Deepgram time to process final audio
                            
                            # Now mark session as inactive to prevent new audio processing
                            # BUT keep WebSocket active - we need it to send the next question
                            websocket_handler._live_session_active[interview_id] = False
                            
                            # Stop keepalive (no longer needed after we finish the session)
                            # But WebSocket stays connected!
                            websocket_handler._stop_keepalive(interview_id)
                            
                            # Stop Deepgram Live session gracefully (but keep WebSocket connected)
                            logger.info(f"[Stop Recording] Stopping Deepgram Live session for {interview_id} (WebSocket stays connected)")
                            try:
                                await websocket_handler.stop_live_session(interview_id)
                            except Exception as e:
                                logger.error(f"[Stop Recording] Error stopping Deepgram session: {e}", exc_info=True)
                                # Continue anyway - we can still process the answer
                            
                            # CRITICAL: Ensure WebSocket is still marked as active
                            # Don't mark as disconnected - we need it for the next question
                            if interview_id not in manager.active_connections:
                                logger.error(f"[Stop Recording] ⚠️ WebSocket was removed from manager for {interview_id} - this should not happen!")
                            else:
                                logger.info(f"[Stop Recording] ✓ WebSocket still active for {interview_id} - ready for next question")
                            
                            # Wait a bit more for any final transcripts to arrive (Deepgram might still be processing)
                            await asyncio.sleep(0.5)
                            
                            accumulated_text = websocket_handler.get_accumulated_transcript(interview_id)
                            logger.info(f"🛑 Stop recording requested for {interview_id}, accumulated transcript: '{accumulated_text}' (length: {len(accumulated_text)})")
                            
                            if accumulated_text and len(accumulated_text.strip()) > 0:
                                # Submit answer using accumulated transcript
                                response = await websocket_handler.handle_answer_submission(
                                    interview_id,
                                    {"answer": accumulated_text.strip()}
                                )
                                # Clear accumulated transcript after submission
                                websocket_handler.clear_accumulated_transcript(interview_id)
                                
                                # Send response to frontend (same as answer handler)
                                if response and response.get("type") == "answer_response":
                                    await manager.send_message(interview_id, {
                                        "type": "evaluation",
                                        "evaluation": response.get("evaluation")
                                    })
                                    
                                    if response.get("next_question"):
                                        next_question = response.get("next_question")
                                        next_question_id = next_question.get("question_id")
                                        
                                        await manager.send_message(interview_id, {
                                            "type": "question",
                                            "question": next_question
                                        })
                                        
                                        if next_question_id:
                                            manager.mark_question_sent(interview_id, next_question_id)
                                        
                                        if response.get("flow_state"):
                                            await manager.send_message(interview_id, {
                                                "type": "flow_state",
                                                "state": response.get("flow_state")
                                            })
                                        
                                        # Generate and send TTS audio
                                        try:
                                            from shared.providers.deepgram_client import deepgram_client
                                            import base64
                                            
                                            # Use tts_text from context if available
                                            question_context = next_question.get("context", {})
                                            tts_text = question_context.get("tts_text") if isinstance(question_context, dict) else None
                                            audio_text = tts_text if tts_text else next_question.get("question", "")
                                            
                                            logger.info(f"🎵 TTS: {'Using tts_summary' if tts_text else 'Using full question'}")
                                            
                                            audio_bytes = await deepgram_client.synthesize_speech(
                                                text=audio_text,
                                                model="aura-asteria-en",
                                                voice="asteria"
                                            )
                                            
                                            if audio_bytes:
                                                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                                                await manager.send_message(interview_id, {
                                                    "type": "audio",
                                                    "audio": audio_base64,
                                                    "format": "mp3"
                                                })
                                            else:
                                                logger.warning("⚠️ TTS returned empty audio bytes")
                                        except Exception as e:
                                            logger.error(f"❌ Error generating TTS: {e}", exc_info=True)
                                
                                elif response and response.get("type") == "completed":
                                    await manager.send_message(interview_id, {
                                        "type": "completed",
                                        "evaluation": response.get("evaluation"),
                                        "message": response.get("message")
                                    })
                                
                                elif response and response.get("type") == "error":
                                    await manager.send_message(interview_id, {
                                        "type": "error",
                                        "message": response.get("message")
                                    })
                            else:
                                logger.warning(f"⚠️ No accumulated transcript for {interview_id} when stop_recording requested")
                                await manager.send_message(interview_id, {
                                    "type": "error",
                                    "message": "No transcript available. Please try speaking again."
                                })
                    except Exception as e:
                        # CRITICAL: Log full exception to see what's causing the failure
                        logger.error(f"[Stop Recording] ✗✗✗ EXCEPTION handling stop_recording for {interview_id}: {e}", exc_info=True)
                        logger.error(f"[Stop Recording] This exception may have caused the WebSocket to close! Check stack trace above.")
                        
                        # Try to send error message, but don't fail if WebSocket is already closed
                        try:
                            await manager.send_message(interview_id, {
                                "type": "error",
                                "message": f"Error processing answer: {str(e)}"
                            })
                        except Exception as send_error:
                            logger.error(f"[Stop Recording] Could not send error message to frontend: {send_error}")
                            # WebSocket might already be closed - that's OK, just log it
                
                elif message_type == "submit_answer":
                    # New simplified handler for direct Deepgram STT
                    # The frontend sends the transcript directly, no need for backend audio processing
                    try:
                        logger.info(f"📝 Submit answer requested for {interview_id} (direct Deepgram STT)")
                        answer_data = data.get("data", {})
                        answer_text = answer_data.get("answer", "")
                        
                        logger.info(f"Received answer: '{answer_text}' (length: {len(answer_text)})")
                        
                        if answer_text and len(answer_text.strip()) > 0:
                            # Submit answer using provided transcript
                            response = await websocket_handler.handle_answer_submission(
                                interview_id,
                                {"answer": answer_text.strip()}
                            )
                            
                            # Send response to frontend
                            if response and response.get("type") == "answer_response":
                                await manager.send_message(interview_id, {
                                    "type": "evaluation",
                                    "evaluation": response.get("evaluation")
                                })
                                
                                if response.get("next_question"):
                                    next_question = response.get("next_question")
                                    next_question_id = next_question.get("question_id")
                                    
                                    await manager.send_message(interview_id, {
                                        "type": "question",
                                        "question": next_question
                                    })
                                    
                                    if next_question_id:
                                        manager.mark_question_sent(interview_id, next_question_id)
                                    
                                    if response.get("flow_state"):
                                        await manager.send_message(interview_id, {
                                            "type": "flow_state",
                                            "state": response.get("flow_state")
                                        })
                                    
                                    # Generate and send TTS audio
                                    try:
                                        from shared.providers.deepgram_client import deepgram_client
                                        import base64
                                        
                                        # Use tts_text from context if available (for coding questions)
                                        # Otherwise use full question text
                                        question_context = next_question.get("context", {})
                                        tts_text = question_context.get("tts_text") if isinstance(question_context, dict) else None
                                        audio_text = tts_text if tts_text else next_question.get("question")
                                        
                                        logger.info(f"🎵 TTS: {'Using tts_summary' if tts_text else 'Using full question'}")
                                        
                                        audio_data = await deepgram_client.synthesize_speech(audio_text)
                                        
                                        if audio_data:
                                            # Convert bytes to base64 for JSON serialization
                                            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                                            await manager.send_message(interview_id, {
                                                "type": "audio",
                                                "audio": audio_base64
                                            })
                                        else:
                                            logger.warning(f"No TTS audio generated for interview {interview_id}")
                                    except Exception as tts_error:
                                        logger.error(f"TTS generation failed: {tts_error}")
                                        # Continue anyway - user can read the question
                                
                                elif response.get("interview_completed"):
                                    await manager.send_message(interview_id, {
                                        "type": "completed",
                                        "message": "Interview completed successfully"
                                    })
                                    
                                    # Stop keepalive task before disconnecting
                                    websocket_handler._stop_keepalive(interview_id)
                                    
                                    # Generate report asynchronously (don't block)
                                    logger.info(f"📊 Triggering report generation for interview {interview_id}")
                                    try:
                                        from interview_service.report_generator import generate_interview_report
                                        state = await load_interview_state(interview_id)
                                        if state:
                                            profile_data = await firestore_client.get_document("users", state.user_id)
                                            
                                            # Wrap in async function to catch errors
                                            async def _generate_report_with_logging():
                                                try:
                                                    result = await generate_interview_report(interview_id, state, profile_data)
                                                    if result:
                                                        logger.info(f"✅ Report successfully generated for {interview_id}")
                                                    else:
                                                        logger.error(f"❌ Report generation returned None for {interview_id}")
                                                except Exception as e:
                                                    logger.error(f"❌ Report generation FAILED for {interview_id}: {e}", exc_info=True)
                                            
                                            asyncio.create_task(_generate_report_with_logging())
                                            logger.info(f"✅ Report generation task created for {interview_id}")
                                        else:
                                            logger.error(f"❌ Could not load interview state for report: {interview_id}")
                                    except Exception as report_error:
                                        logger.error(f"Failed to start report generation: {report_error}", exc_info=True)
                                    
                                    # Close WebSocket gracefully after interview completion
                                    logger.info(f"Interview completed, closing WebSocket for {interview_id}")
                                    manager.disconnect(interview_id)
                            else:
                                logger.warning(f"No response from answer submission for {interview_id}")
                        else:
                            logger.warning(f"Empty answer received for {interview_id}")
                            await manager.send_message(interview_id, {
                                "type": "error",
                                "message": "No answer provided. Please try again."
                            })
                    except Exception as e:
                        logger.error(f"Error processing submitted answer: {e}", exc_info=True)
                        try:
                            await manager.send_message(interview_id, {
                                "type": "error",
                                "message": f"Error processing answer: {str(e)}"
                            })
                        except Exception as send_error:
                            logger.error(f"Could not send error message to frontend: {send_error}")
                
                elif message_type == "answer":
                    # Handle answer submission via WebSocket handler
                    try:
                        answer_data = data.get("data", {})
                        response = await websocket_handler.handle_answer_submission(
                            interview_id,
                            answer_data
                        )
                        
                        if response:
                            # Send evaluation
                            if response.get("type") == "answer_response":
                                await manager.send_message(interview_id, {
                                    "type": "evaluation",
                                    "evaluation": response.get("evaluation")
                                })
                                
                                # Send next question
                                if response.get("next_question"):
                                    next_question = response.get("next_question")
                                    next_question_id = next_question.get("question_id")
                                    
                                    await manager.send_message(interview_id, {
                                        "type": "question",
                                        "question": next_question
                                    })
                                    
                                    # Mark new question as sent
                                    if next_question_id:
                                        manager.mark_question_sent(interview_id, next_question_id)
                                    
                                    # Send flow state update
                                    if response.get("flow_state"):
                                        await manager.send_message(interview_id, {
                                            "type": "flow_state",
                                            "state": response.get("flow_state")
                                        })
                                    
                                    # Generate and send TTS audio for next question
                                    try:
                                        from shared.providers.deepgram_client import deepgram_client
                                        import base64
                                        
                                        # Use tts_text from context if available
                                        question_context = next_question.get("context", {})
                                        tts_text = question_context.get("tts_text") if isinstance(question_context, dict) else None
                                        audio_text = tts_text if tts_text else next_question.get("question", "")
                                        
                                        logger.info(f"🎵 TTS: {'Using tts_summary' if tts_text else 'Using full question'}")
                                        
                                        audio_bytes = await deepgram_client.synthesize_speech(
                                            text=audio_text,
                                            model="aura-asteria-en",
                                            voice="asteria"
                                        )
                                        
                                        if audio_bytes:
                                            logger.info(f"✓ TTS generated successfully, size: {len(audio_bytes)} bytes")
                                            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                                            await manager.send_message(interview_id, {
                                                "type": "audio",
                                                "audio": audio_base64,
                                                "format": "mp3"
                                            })
                                            logger.info(f"✓ TTS audio sent to frontend")
                                        else:
                                            logger.warning("⚠️ TTS returned empty audio bytes")
                                    except Exception as e:
                                        logger.error(f"❌ Error generating TTS for next question: {e}", exc_info=True)
                                        # Non-critical, continue without audio
                            
                            elif response.get("type") == "completed":
                                await manager.send_message(interview_id, {
                                    "type": "completed",
                                    "evaluation": response.get("evaluation"),
                                    "message": response.get("message")
                                })
                                
                                # Stop keepalive task before disconnecting
                                websocket_handler._stop_keepalive(interview_id)
                                
                                # Generate report asynchronously (don't block)
                                logger.info(f"📊 Triggering report generation for interview {interview_id}")
                                try:
                                    from interview_service.report_generator import generate_interview_report
                                    state = await load_interview_state(interview_id)
                                    if state:
                                        profile_data = await firestore_client.get_document("users", state.user_id)
                                        
                                        # Wrap in async function to catch errors
                                        async def _generate_report_with_logging_2():
                                            try:
                                                result = await generate_interview_report(interview_id, state, profile_data)
                                                if result:
                                                    logger.info(f"✅ Report successfully generated for {interview_id}")
                                                else:
                                                    logger.error(f"❌ Report generation returned None for {interview_id}")
                                            except Exception as e:
                                                logger.error(f"❌ Report generation FAILED for {interview_id}: {e}", exc_info=True)
                                        
                                        asyncio.create_task(_generate_report_with_logging_2())
                                        logger.info(f"✅ Report generation task created for {interview_id}")
                                    else:
                                        logger.error(f"❌ Could not load interview state for report: {interview_id}")
                                except Exception as report_error:
                                    logger.error(f"Failed to start report generation: {report_error}", exc_info=True)
                                
                                # Close WebSocket gracefully after interview completion
                                logger.info(f"Interview completed, closing WebSocket for {interview_id}")
                                manager.disconnect(interview_id)
                            
                            elif response.get("type") == "error":
                                await manager.send_message(interview_id, {
                                    "type": "error",
                                    "message": response.get("message")
                                })
                    except Exception as e:
                        logger.error(f"Error processing answer: {e}")
                        # Don't break connection, send error to client
                        try:
                            await manager.send_message(interview_id, {
                                "type": "error",
                                "message": f"Error processing answer: {str(e)}"
                            })
                        except:
                            pass
                
                elif message_type == "speech_end":
                    # Handle silence detection - finalize answer automatically
                    try:
                        # Get accumulated transcript
                        accumulated_text = websocket_handler.get_accumulated_transcript(interview_id)
                        
                        if accumulated_text and len(accumulated_text.strip()) > 10:
                            # Auto-submit answer on silence detection
                            logger.info(f"Auto-submitting answer on silence detection for interview {interview_id}")
                            
                            # Submit answer using accumulated transcript
                            answer_data = {
                                "answer": accumulated_text.strip()
                            }
                            
                            response = await websocket_handler.handle_answer_submission(
                                interview_id,
                                answer_data
                            )
                            
                            if response:
                                # Send evaluation
                                if response.get("type") == "answer_response":
                                    await manager.send_message(interview_id, {
                                        "type": "evaluation",
                                        "evaluation": response.get("evaluation")
                                    })
                                    
                                    # Send next question
                                    if response.get("next_question"):
                                        next_question = response.get("next_question")
                                        next_question_id = next_question.get("question_id")
                                        
                                        await manager.send_message(interview_id, {
                                            "type": "question",
                                            "question": next_question
                                        })
                                        
                                        # Mark new question as sent
                                        if next_question_id:
                                            manager.mark_question_sent(interview_id, next_question_id)
                                        
                                        # Send flow state update
                                        if response.get("flow_state"):
                                            await manager.send_message(interview_id, {
                                                "type": "flow_state",
                                                "state": response.get("flow_state")
                                            })
                                        
                                        # Generate and send TTS audio for next question (speech_end handler)
                                        try:
                                            from shared.providers.deepgram_client import deepgram_client
                                            import base64
                                            
                                            # Use tts_text from context if available
                                            question_context = next_question.get("context", {})
                                            tts_text = question_context.get("tts_text") if isinstance(question_context, dict) else None
                                            audio_text = tts_text if tts_text else next_question.get("question", "")
                                            
                                            logger.info(f"🎵 TTS: {'Using tts_summary' if tts_text else 'Using full question'}")
                                            
                                            audio_bytes = await deepgram_client.synthesize_speech(
                                                text=audio_text,
                                                model="aura-asteria-en",
                                                voice="asteria"
                                            )
                                            
                                            if audio_bytes:
                                                logger.info(f"✓ TTS generated successfully, size: {len(audio_bytes)} bytes")
                                                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                                                await manager.send_message(interview_id, {
                                                    "type": "audio",
                                                    "audio": audio_base64,
                                                    "format": "mp3"
                                                })
                                                logger.info(f"✓ TTS audio sent to frontend")
                                            else:
                                                logger.warning("⚠️ TTS returned empty audio bytes")
                                        except Exception as e:
                                            logger.error(f"❌ Error generating TTS (speech_end): {e}", exc_info=True)
                                
                                elif response.get("type") == "completed":
                                    await manager.send_message(interview_id, {
                                        "type": "completed",
                                        "evaluation": response.get("evaluation"),
                                        "message": response.get("message")
                                    })
                                
                                elif response.get("type") == "error":
                                    await manager.send_message(interview_id, {
                                        "type": "error",
                                        "message": response.get("message")
                                    })
                        else:
                            # Accumulated text is too short - don't auto-submit
                            logger.debug(f"Accumulated text too short for auto-submit: {len(accumulated_text) if accumulated_text else 0} chars")
                    except Exception as e:
                        logger.error(f"Error processing speech_end: {e}")
                        try:
                            await manager.send_message(interview_id, {
                                "type": "error",
                                "message": f"Error processing speech end: {str(e)}"
                            })
                        except:
                            pass
                
                elif message_type == "ping":
                    # Heartbeat
                    try:
                        await manager.send_message(interview_id, {"type": "pong"})
                    except Exception as e:
                        logger.error(f"Error sending pong: {e}")
                
                elif message_type == "get_current_question":
                    # Client requests current question (for reconnection)
                    try:
                        state = await load_interview_state(interview_id)
                        if state and state.current_question:
                            await manager.send_message(interview_id, {
                                "type": "question",
                                "question": state.current_question.model_dump()
                            })
                            
                            # Generate and send TTS audio
                            try:
                                from shared.providers.deepgram_client import deepgram_client
                                import base64
                                
                                # Use tts_text from context if available
                                question_context = state.current_question.context or {}
                                tts_text = question_context.get("tts_text") if isinstance(question_context, dict) else None
                                audio_text = tts_text if tts_text else state.current_question.question
                                
                                logger.info(f"🎵 TTS: {'Using tts_summary' if tts_text else 'Using full question'}")
                                
                                audio_bytes = await deepgram_client.synthesize_speech(
                                    text=audio_text,
                                    model="aura-asteria-en",
                                    voice="asteria"
                                )
                                
                                if audio_bytes:
                                    logger.info(f"✓ TTS generated successfully, size: {len(audio_bytes)} bytes")
                                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                                    await manager.send_message(interview_id, {
                                        "type": "audio",
                                    "audio": audio_base64,
                                    "format": "mp3"
                                    })
                                    logger.info(f"✓ TTS audio sent to frontend")
                                else:
                                    logger.warning("⚠️ TTS returned empty audio bytes")
                            except Exception as e:
                                logger.error(f"❌ Error generating TTS for current question request: {e}", exc_info=True)
                        else:
                            await manager.send_message(interview_id, {
                                "type": "error",
                                "message": "No current question available"
                            })
                    except Exception as e:
                        logger.error(f"Error handling get_current_question: {e}")
                        try:
                            await manager.send_message(interview_id, {
                                "type": "error",
                                "message": f"Error loading current question: {str(e)}"
                            })
                        except:
                            pass
                else:
                    # Unknown message type
                    logger.warning(f"Unknown message type: {message_type} from {interview_id}")
                    try:
                        await manager.send_message(interview_id, {
                            "type": "error",
                            "message": f"Unknown message type: {message_type}"
                        })
                    except:
                        pass
        except WebSocketDisconnect as e:
            # WebSocket disconnected - this should be caught in the inner loop, but handle here too
            disconnect_code = e.code if hasattr(e, 'code') else 1000
            logger.info(f"WebSocket disconnected: {interview_id}, code: {disconnect_code}, reason: {getattr(e, 'reason', 'unknown')}")
            if interview_id in manager.active_connections:
                # Only remove if this is the same connection
                if manager.active_connections[interview_id] == websocket:
                    del manager.active_connections[interview_id]
                    logger.info(f"WebSocket removed from manager: {interview_id}")
        except Exception as e:
            logger.error(f"WebSocket error for interview {interview_id}: {e}")
            import traceback
            logger.error(f"WebSocket traceback: {traceback.format_exc()}")
            # Don't try to send error message if connection is broken
    finally:
        # Cancel ping task if it's still running
        if ping_task and not ping_task.done():
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass
            logger.debug(f"✓ Cancelled WebSocket ping task for {interview_id}")
        
        # CRITICAL: Stop keepalive task to prevent "no ping received" warnings
        websocket_handler._stop_keepalive(interview_id)
        logger.info(f"✓ Stopped keepalive task for {interview_id}")
        
        # Mark as disconnected and stop Deepgram session
        websocket_handler.mark_websocket_disconnected(interview_id)
        # Clean up connection only if it's still in the manager and matches
        if interview_id in manager.active_connections and manager.active_connections[interview_id] == websocket:
            try:
                # Try to close gracefully
                await websocket.close(code=1000, reason="Connection cleanup")
            except Exception as e:
                logger.debug(f"Error closing WebSocket during cleanup: {e}")
            finally:
                if interview_id in manager.active_connections:
                    del manager.active_connections[interview_id]
                # Clean up ping time tracking
                if interview_id in manager.last_ping_time:
                    del manager.last_ping_time[interview_id]
            logger.info(f"WebSocket connection cleaned up: {interview_id} (Remaining: {len(manager.active_connections)})")


@app.get("/api/interviews/{interview_id}/deepgram-token")
async def get_deepgram_token(interview_id: str):
    """
    Get a temporary Deepgram API key for client-side STT.
    This allows the frontend to connect directly to Deepgram without proxying audio through the backend.
    
    Returns:
        - api_key: Temporary Deepgram API key (valid for 5 minutes)
        - expires_in: Seconds until expiration
    """
    try:
        # Verify interview exists
        state = await load_interview_state(interview_id)
        if not state:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        # Get a Deepgram API key from the pool
        from shared.providers.deepgram_client import deepgram_client
        from shared.providers.pool_manager import provider_pool_manager, ProviderType
        
        # Get an account from the pool
        account = await provider_pool_manager.get_account(ProviderType.DEEPGRAM_STT)
        
        if not account or not account.api_key:
            logger.error("No Deepgram API key available")
            raise HTTPException(status_code=503, detail="STT service temporarily unavailable")
        
        # Return the actual Deepgram API key for client-side STT
        # This is safe because:
        # 1. The key is scoped to the interview (user must be authenticated)
        # 2. The key is from a pool and can be rotated
        # 3. Frontend needs direct Deepgram connection for real-time STT
        logger.info(f"Deepgram API key provided for interview {interview_id}")
        
        return {
            "api_key": account.api_key,  # Return actual API key (frontend expects this field name)
            "expires_in": 300,  # 5 minutes (informational - Deepgram keys don't actually expire this quickly)
            "model": "nova-2",
            "language": "en-US"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Deepgram token: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting STT token: {str(e)}")


@app.get("/api/debug/config")
async def debug_config():
    """Debug endpoint to check configuration (for troubleshooting - no auth required)."""
    from shared.config.settings import settings
    
    return {
        "redis_connected": redis_client.redis is not None,
        "gemini_api_keys_set": bool(settings.GEMINI_API_KEYS),
        "deepgram_api_keys_set": bool(settings.DEEPGRAM_API_KEYS),
        "redis_url": settings.REDIS_URL,
        "environment": settings.ENVIRONMENT,
        "gemini_key_length": len(settings.GEMINI_API_KEYS) if settings.GEMINI_API_KEYS else 0,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        # CRITICAL: Disable WebSocket ping timeout to prevent Uvicorn from closing connections
        # Frontend sends JSON ping messages, but Uvicorn expects protocol-level PING frames
        # Setting high timeout prevents premature WebSocket closure
        ws_ping_interval=20,  # Send ping every 20 seconds
        ws_ping_timeout=120,  # Wait 120 seconds for pong before closing (effectively disabled)
    )