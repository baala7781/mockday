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
        
        # Option 1: JSON content in environment variable (for Railway/cloud deployments)
        json_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if json_creds:
            try:
                creds_dict = json.loads(json_creds)
                cred = credentials.Certificate(creds_dict)
                # Extract project_id from credentials for options
                project_id = creds_dict.get("project_id")
                print(f"Firebase: Using credentials from GOOGLE_APPLICATION_CREDENTIALS_JSON (project: {project_id})")
            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON: {e}")
                creds_dict = None
                project_id = None
        else:
            creds_dict = None
            project_id = None
        
        # Option 2: File path in environment variable
        if not cred and settings.GOOGLE_APPLICATION_CREDENTIALS:
            if os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
                print("Firebase: Using credentials from GOOGLE_APPLICATION_CREDENTIALS file")
            else:
                cred = credentials.ApplicationDefault()
                print("Firebase: Using Application Default Credentials")
        
        # Option 3: Default file path
        if not cred and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            print("Firebase: Using credentials from FIREBASE_CREDENTIALS_PATH")
            # Try to extract project_id from file
            try:
                with open(settings.FIREBASE_CREDENTIALS_PATH, 'r') as f:
                    file_creds = json.load(f)
                    project_id = file_creds.get("project_id")
            except:
                project_id = None
        
        options = {}
        # Set project_id explicitly (required for Firebase Auth)
        if project_id:
            options["projectId"] = project_id
        elif settings.FIREBASE_STORAGE_BUCKET:
            # Extract project_id from storage bucket if available
            bucket_parts = settings.FIREBASE_STORAGE_BUCKET.split('.')
            if len(bucket_parts) > 0:
                options["projectId"] = bucket_parts[0]
        
        if settings.FIREBASE_STORAGE_BUCKET:
            options["storageBucket"] = settings.FIREBASE_STORAGE_BUCKET
        
        if cred:
            initialize_app(cred, options or None)
            print("Firebase: Initialization successful!")
        else:
            if options:
                initialize_app(options=options)
            else:
                print("Warning: Firebase credentials not found. Some features may not work.")
    except Exception as e:
        print(f"Warning: Firebase initialization failed: {e}")


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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
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

