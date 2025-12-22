"""Interview state management."""
from typing import Optional, Dict, Any
from interview_service.models import (
    InterviewState, InterviewStatus, InterviewPhase, DifficultyLevel,
    Question, Evaluation, SkillWeight, ResumeData, InterviewRole, InterviewFlowState
)
from shared.db.redis_client import redis_client
from shared.db.firestore_client import firestore_client
import json
import uuid
from datetime import datetime


async def create_interview_state(
    user_id: str,
    role: InterviewRole,
    resume_data: ResumeData,
    skill_weights: list[SkillWeight],
    max_questions: int = 15
) -> InterviewState:
    """
    Create a new interview state.
    
    Args:
        user_id: User ID
        role: Interview role
        resume_data: Resume data
        skill_weights: Calculated skill weights
        max_questions: Maximum number of questions
        
    Returns:
        Interview state
    """
    interview_id = str(uuid.uuid4())
    
    state = InterviewState(
        interview_id=interview_id,
        user_id=user_id,
        role=role,
        status=InterviewStatus.NOT_STARTED,
        current_phase=InterviewPhase.INTRODUCTION,
        flow_state=InterviewFlowState.USER_WAITING,  # Initial state: waiting for first question
        resume_data=resume_data,
        skill_weights=skill_weights,
        current_difficulty=DifficultyLevel.BASIC,
        max_questions=max_questions,
        started_at=None,
        completed_at=None,
        phase_questions={},
        interview_duration_minutes=30,  # Default 30 minutes
        conversation_history=[],  # Empty initially
        max_context_pairs=5  # Keep last 5 QA pairs
    )
    
    # Save to Redis
    await save_interview_state(state)
    
    # Also save to Firestore for persistence
    await save_interview_state_to_firestore(state)
    
    return state


async def save_interview_state(state: InterviewState) -> bool:
    """
    Save interview state to Redis.
    
    Args:
        state: Interview state
        
    Returns:
        True if saved successfully
    """
    try:
        key = f"interview:{state.interview_id}"
        # Convert to dict for JSON serialization
        state_dict = state.model_dump(mode='json')
        # Convert datetime to string (check if it's already a string)
        if state_dict.get("started_at"):
            if not isinstance(state_dict["started_at"], str):
                # It's a datetime object, convert to ISO string
                state_dict["started_at"] = state_dict["started_at"].isoformat()
        if state_dict.get("completed_at"):
            if not isinstance(state_dict["completed_at"], str):
                # It's a datetime object, convert to ISO string
                state_dict["completed_at"] = state_dict["completed_at"].isoformat()
        
        # Calculate TTL based on interview duration + buffer
        # If interview started, calculate remaining time + buffer
        # If not started, use default duration + buffer
        ttl_seconds = 3600  # Default 1 hour
        if state.started_at:
            from datetime import datetime
            if isinstance(state.started_at, str):
                started = datetime.fromisoformat(state.started_at.replace('Z', '+00:00'))
            else:
                started = state.started_at
            elapsed = (datetime.now(started.tzinfo) - started).total_seconds()
            remaining = (state.interview_duration_minutes * 60) - elapsed
            # Add 30 minute buffer for post-interview processing
            ttl_seconds = int(max(remaining + 1800, 3600))  # At least 1 hour
        
        # Extend TTL on every update (touch key methodology)
        await redis_client.set(key, state_dict, expire=ttl_seconds)
        return True
    except Exception as e:
        # Redis errors are non-critical - log but don't fail
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Error saving interview state to Redis (non-critical): {e}")
        return False


async def load_interview_state(interview_id: str) -> Optional[InterviewState]:
    """
    Load interview state from Redis with Firestore fallback and cache hydration.
    
    Args:
        interview_id: Interview ID
        
    Returns:
        Interview state or None if not found
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Try Redis first (fast cache)
    try:
        key = f"interview:{interview_id}"
        state_dict = await redis_client.get(key)
        
        if state_dict:
            try:
                # Convert back to InterviewState
                state = InterviewState(**state_dict)
                return state
            except Exception as e:
                # Partial corruption - try Firestore fallback
                logger.debug(f"Error deserializing Redis state (partial corruption): {e}")
    except Exception as e:
        # Redis errors are non-critical - log at debug level
        logger.debug(f"Error loading interview state from Redis (non-critical): {e}")
    
    # Fallback to Firestore
    try:
        state_dict = await firestore_client.get_document(
            collection="interviews",
            document_id=interview_id
        )
        
        if state_dict:
            try:
                # Handle missing fields gracefully
                state = InterviewState(**state_dict)
                
                # Hydrate Redis cache back (extend TTL)
                try:
                    key = f"interview:{interview_id}"
                    ttl_seconds = 3600  # Default 1 hour
                    if state.started_at:
                        from datetime import datetime
                        if isinstance(state.started_at, str):
                            started = datetime.fromisoformat(state.started_at.replace('Z', '+00:00'))
                        else:
                            started = state.started_at
                        elapsed = (datetime.now(started.tzinfo) - started).total_seconds()
                        remaining = (state.interview_duration_minutes * 60) - elapsed
                        ttl_seconds = int(max(remaining + 1800, 3600))
                    
                    state_dict_serialized = state.model_dump(mode='json')
                    # Convert datetime to string
                    if state_dict_serialized.get("started_at") and not isinstance(state_dict_serialized["started_at"], str):
                        state_dict_serialized["started_at"] = state_dict_serialized["started_at"].isoformat()
                    if state_dict_serialized.get("completed_at") and not isinstance(state_dict_serialized["completed_at"], str):
                        state_dict_serialized["completed_at"] = state_dict_serialized["completed_at"].isoformat()
                    
                    await redis_client.set(key, state_dict_serialized, expire=ttl_seconds)
                    logger.debug(f"Hydrated Redis cache from Firestore for interview: {interview_id}")
                except Exception as cache_error:
                    # Non-critical - cache hydration failed
                    logger.debug(f"Error hydrating Redis cache (non-critical): {cache_error}")
                
                return state
            except Exception as e:
                logger.error(f"Error deserializing Firestore state: {e}")
                return None
    except Exception as e:
        # Firestore errors are non-critical - log at debug level
        logger.debug(f"Error loading interview state from Firestore (non-critical): {e}")
    
    return None


async def save_interview_state_to_firestore(state: InterviewState) -> bool:
    """
    Save interview state to Firestore for persistence.
    
    Args:
        state: Interview state
        
    Returns:
        True if saved successfully, False otherwise (non-blocking)
    """
    try:
        # Firestore is optional - if it fails, we continue with Redis only
        if not firestore_client.db:
            # Firestore not initialized, skip silently
            return False
        
        state_dict = state.model_dump(mode='json')
        # Convert datetime to ISO string (check if it's already a string)
        if state_dict.get("started_at"):
            if not isinstance(state_dict["started_at"], str):
                # It's a datetime object, convert to ISO string
                state_dict["started_at"] = state_dict["started_at"].isoformat()
        if state_dict.get("completed_at"):
            if not isinstance(state_dict["completed_at"], str):
                # It's a datetime object, convert to ISO string
                state_dict["completed_at"] = state_dict["completed_at"].isoformat()
        
        # Save to Firestore (non-blocking - don't fail if this errors)
        result = await firestore_client.set_document(
            collection="interviews",
            document_id=state.interview_id,
            data=state_dict,
            merge=True
        )
        return result
    except Exception as e:
        # Firestore errors are non-critical - log but don't fail
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Warning: Failed to save interview state to Firestore (non-critical): {e}")
        return False


async def load_interview_state_from_firestore(interview_id: str) -> Optional[InterviewState]:
    """
    Load interview state from Firestore.
    
    Args:
        interview_id: Interview ID
        
    Returns:
        Interview state or None if not found
    """
    try:
        state_dict = await firestore_client.get_document(
            collection="interviews",
            document_id=interview_id
        )
        
        if state_dict:
            return InterviewState(**state_dict)
    except Exception as e:
        # Firestore errors are non-critical - log at debug level
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Error loading interview state from Firestore (non-critical): {e}")
    
    return None


async def update_interview_state(
    interview_id: str,
    updates: Dict[str, Any]
) -> Optional[InterviewState]:
    """
    Update interview state.
    
    Args:
        interview_id: Interview ID
        updates: Dictionary of updates
        
    Returns:
        Updated interview state or None if not found
    """
    state = await load_interview_state(interview_id)
    if not state:
        return None
    
    # Update state
    for key, value in updates.items():
        if hasattr(state, key):
            setattr(state, key, value)
    
    # Save updated state
    await save_interview_state(state)
    await save_interview_state_to_firestore(state)
    
    return state


async def start_interview(interview_id: str) -> Optional[InterviewState]:
    """Mark interview as started."""
    return await update_interview_state(
        interview_id,
        {
            "status": InterviewStatus.IN_PROGRESS,
            "started_at": datetime.now()
        }
    )


async def complete_interview(interview_id: str) -> Optional[InterviewState]:
    """Mark interview as completed."""
    return await update_interview_state(
        interview_id,
        {
            "status": InterviewStatus.COMPLETED,
            "completed_at": datetime.now()
        }
    )


async def add_answer_to_state(
    interview_id: str,
    skill: str,
    evaluation: Evaluation,
    question: Question
) -> Optional[InterviewState]:
    """Add answer evaluation to interview state."""
    state = await load_interview_state(interview_id)
    if not state:
        return None
    
    # Add evaluation to answered skills
    if skill not in state.answered_skills:
        state.answered_skills[skill] = []
    state.answered_skills[skill].append(evaluation)
    
    # Update current difficulty
    state.current_difficulty = evaluation.next_difficulty
    
    # Add question to asked questions
    state.questions_asked.append(question)
    state.total_questions += 1
    
    # Update current question and skill
    state.current_question = None
    state.current_skill = None
    
    # Save state
    await save_interview_state(state)
    await save_interview_state_to_firestore(state)
    
    return state

