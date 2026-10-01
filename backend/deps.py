"""
Shared FastAPI dependencies
===========================
Helpers that endpoints use to resolve the current user from a bearer token.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User
from services.auth import verify_jwt_token

# auto_error=False lets us return our own 401 JSON instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = "Not signed in. Sign in with Google to continue."


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Require a valid JWT and return the matching user, else raise 401."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=CREDENTIALS_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_jwt_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    user = db.get(User, int(user_id)) if user_id else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the current user if a valid token is present, otherwise None.

    Used by endpoints that work for both signed-in and anonymous visitors.
    """
    if credentials is None:
        return None
    payload = verify_jwt_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None
    return db.get(User, int(payload["sub"]))
