"""Firebase authentication utilities for FastAPI."""
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, initialize_app, get_app
import firebase_admin
import os
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
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            cred = credentials.ApplicationDefault()
        elif os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        
        options = {}
        if settings.FIREBASE_STORAGE_BUCKET:
            options["storageBucket"] = settings.FIREBASE_STORAGE_BUCKET
        
        if cred:
            initialize_app(cred, options or None)
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

