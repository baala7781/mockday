"""Firebase authentication utilities for FastAPI."""
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, initialize_app, get_app
import firebase_admin
import os
import json
from typing import Optional
from shared.config.settings import settings


# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    try:
        # Check if Firebase is already initialized
        try:
            get_app()
            # Already initialized
            return
        except ValueError:
            # Not initialized, proceed to initialize
            pass
        
        cred = None
        project_id = None
        
        # CRITICAL: Unset GOOGLE_APPLICATION_CREDENTIALS if it's set to JSON string
        # Firebase SDK expects this to be a FILE PATH, not JSON content
        # If it's set to JSON, it will try to read it as a file and fail
        google_app_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if google_app_creds and google_app_creds.strip().startswith("{"):
            # It's JSON, not a file path - temporarily unset it
            print("CRITICAL: GOOGLE_APPLICATION_CREDENTIALS contains JSON (not file path). Temporarily unsetting to prevent Firebase from reading it as a file.")
            # Temporarily remove from environment to prevent Firebase SDK from using it
            if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
                original_creds = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS")
                print("Temporarily removed GOOGLE_APPLICATION_CREDENTIALS from environment")
        
        # Option 1: JSON content in environment variable (for Railway/cloud deployments)
        json_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if json_creds:
            try:
                # Remove any surrounding quotes if present
                json_creds = json_creds.strip().strip('"').strip("'")
                creds_dict = json.loads(json_creds)
                # Extract project_id BEFORE creating credential
                project_id = creds_dict.get("project_id")
                # Create credential from dict (not file path)
                cred = credentials.Certificate(creds_dict)
                print(f"Firebase: Using credentials from GOOGLE_APPLICATION_CREDENTIALS_JSON (project: {project_id})")
            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON: {e}")
                cred = None
                project_id = None
            except Exception as e:
                print(f"Warning: Failed to create Firebase credentials from JSON: {e}")
                cred = None
                project_id = None
        
        # Option 2: File path in environment variable (only if it's actually a file path)
        if not cred and settings.GOOGLE_APPLICATION_CREDENTIALS:
            # Check if it's a file path (not JSON)
            if not settings.GOOGLE_APPLICATION_CREDENTIALS.strip().startswith("{"):
                if os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                    cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
                    print("Firebase: Using credentials from GOOGLE_APPLICATION_CREDENTIALS file")
                else:
                    # Only use Application Default if no JSON creds and file doesn't exist
                    if not json_creds:
                        try:
                            cred = credentials.ApplicationDefault()
                            print("Firebase: Using Application Default Credentials")
                        except Exception as e:
                            print(f"Warning: Application Default Credentials failed: {e}")
                            cred = None
        
        # Option 3: Default file path (only if no JSON creds)
        if not cred and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
            try:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                print("Firebase: Using credentials from FIREBASE_CREDENTIALS_PATH")
                # Try to extract project_id from file
                with open(settings.FIREBASE_CREDENTIALS_PATH, 'r') as f:
                    file_creds = json.load(f)
                    project_id = file_creds.get("project_id")
            except Exception as e:
                print(f"Warning: Failed to load credentials from file: {e}")
                cred = None
        
        options = {}
        # Set project_id explicitly (REQUIRED for Firebase Auth)
        if project_id:
            options["projectId"] = project_id
            print(f"Firebase: Setting projectId to {project_id}")
        elif settings.FIREBASE_STORAGE_BUCKET:
            # Extract project_id from storage bucket if available
            bucket_parts = settings.FIREBASE_STORAGE_BUCKET.split('.')
            if len(bucket_parts) > 0:
                options["projectId"] = bucket_parts[0]
                print(f"Firebase: Extracted projectId from storage bucket: {options['projectId']}")
        
        if settings.FIREBASE_STORAGE_BUCKET:
            options["storageBucket"] = settings.FIREBASE_STORAGE_BUCKET
        
        if cred:
            # CRITICAL: Must pass options with projectId
            if not options.get("projectId") and project_id:
                options["projectId"] = project_id
            
            # Ensure projectId is set
            if not options.get("projectId"):
                print("ERROR: projectId is required but not found in credentials or options")
                raise ValueError("Firebase projectId is required but not found")
            
            # Initialize with explicit credential and options
            # This ensures Firebase uses our credential object, not env vars
            firebase_app = initialize_app(cred, options if options else None, name='[DEFAULT]')
            print(f"Firebase: Initialization successful! Project: {options.get('projectId')}")
            print(f"Firebase: App name: {firebase_app.name}, Credential type: {type(cred).__name__}")
        else:
            # Try to initialize with just options (for Application Default Credentials)
            if options.get("projectId"):
                initialize_app(options=options)
                print(f"Firebase: Initialized with Application Default Credentials. Project: {options.get('projectId')}")
            else:
                error_msg = "ERROR: Firebase credentials not found and projectId not set. Cannot initialize Firebase."
                print(error_msg)
                raise ValueError(error_msg)
    except ValueError:
        # Re-raise ValueError (our custom errors)
        raise
    except Exception as e:
        error_msg = f"Firebase initialization failed: {str(e)}"
        # Don't expose full error to prevent secret leakage
        if "private_key" in str(e).lower() or "service_account" in str(e).lower():
            error_msg = "Firebase initialization failed: Credential configuration error"
        print(f"ERROR: {error_msg}")
        # Don't raise - allow app to start but auth will fail gracefully


# Initialize on import
initialize_firebase()

# HTTP Bearer token scheme
security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verify Firebase ID token and return decoded token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        Decoded Firebase token (dict)
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Check if Firebase is initialized
        try:
            get_app()
        except ValueError:
            # Firebase not initialized
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Firebase not initialized - cannot verify tokens")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable"
            )
        
        token = credentials.credentials
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except Exception as e:
        # NEVER expose sensitive error details in production
        error_msg = str(e)
        # Sanitize error message - remove any credential data
        if "File" in error_msg and "service_account" in error_msg:
            error_msg = "Authentication service configuration error"
        elif "project_id" in error_msg.lower() or "private_key" in error_msg.lower():
            error_msg = "Authentication service configuration error"
        
        # Log full error server-side only (never send to client)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Firebase auth error: {e}", exc_info=True)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Please check your credentials."
        )


async def get_current_user(token: dict = Depends(verify_token)) -> dict:
    """
    Get current authenticated user from token.
    
    Args:
        token: Decoded Firebase token
        
    Returns:
        User information dict
    """
    return {
        "uid": token.get("uid"),
        "email": token.get("email"),
        "name": token.get("name"),
    }

