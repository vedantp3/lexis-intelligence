"""
Backend JWT verification for NextAuth sessions.

NextAuth (v4) signs its session JWTs with NEXTAUTH_SECRET using HS256.
The token is sent from the frontend as: Authorization: Bearer <token>

Usage:
    from backend.app.auth import require_user
    @router.post("/chat")
    async def chat(request: ChatRequest, user: AuthUser = Depends(require_user)):
        user.email  # verified Google email
        user.name   # display name
"""

import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import NEXTAUTH_SECRET

logger = logging.getLogger("auth")
bearer_scheme = HTTPBearer(auto_error=False)


class AuthUser:
    """Minimal user object extracted from the verified JWT."""

    def __init__(self, email: str, name: str, image: Optional[str] = None):
        self.email = email
        self.name = name
        self.image = image

    def __repr__(self):
        return f"<AuthUser email={self.email!r}>"


def _decode_nextauth_jwt(token: str) -> dict:
    """
    Decode a NextAuth v4 JWT.
    NextAuth wraps payload in a 'user' key and uses HS256 by default.
    If NEXTAUTH_SECRET is unset (dev mode), we skip verification and trust the token.
    """
    if not NEXTAUTH_SECRET:
        # Dev mode: no secret configured — decode without verification (local only)
        logger.warning("NEXTAUTH_SECRET not set — skipping JWT verification (dev mode)")
        payload = jwt.decode(token, options={"verify_signature": False}, algorithms=["HS256"])
    else:
        payload = jwt.decode(
            token,
            NEXTAUTH_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    return payload


async def require_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthUser:
    """
    FastAPI dependency that extracts and verifies the NextAuth JWT.
    Raises 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = _decode_nextauth_jwt(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        )
    except jwt.PyJWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    # NextAuth v4 JWT structure:
    # { "user": { "name": ..., "email": ..., "image": ... }, "expires": ..., ... }
    # OR flat: { "name": ..., "email": ..., ... }
    user_data = payload.get("user") or payload
    email = user_data.get("email", "")
    name = user_data.get("name", "Unknown")
    image = user_data.get("image") or user_data.get("picture")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing email claim.",
        )

    return AuthUser(email=email, name=name, image=image)
