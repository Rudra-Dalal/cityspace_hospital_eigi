"""Password hashing, JWT helpers, and RBAC dependency factories."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.database import get_database
from app.utils.logger import get_logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
logger = get_logger(__name__)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    """Gate 1 — authentication. Missing/invalid/expired token → 401."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise JWTError("missing sub")
    except JWTError:
        logger.warning("Authentication failed: invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db = get_database()
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        user = None

    if not user:
        logger.warning("Authentication failed: user %s not found", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.get("is_active") is False:
        logger.warning("Authentication failed: user %s is deactivated", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated. Please contact support.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user["id"] = str(user["_id"])
    return user


# ---------------------------------------------------------------------------
# Generic RBAC factory
# ---------------------------------------------------------------------------

def require_role(*roles: str):
    """Return a FastAPI dependency that allows only users with one of the given roles."""
    async def dep(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if current_user.get("role") not in roles:
            logger.warning(
                "Forbidden: user %s (role=%s) attempted action requiring %s",
                current_user.get("email"),
                current_user.get("role"),
                roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user
    return dep


# ---------------------------------------------------------------------------
# Pre-built RBAC dependencies (use these in route definitions)
# ---------------------------------------------------------------------------

require_super_admin = Depends(require_role("super_admin"))
require_manager_or_above = Depends(require_role("hospital_manager", "super_admin"))
require_doctor = Depends(require_role("doctor", "hospital_manager", "super_admin"))
require_customer = Depends(require_role("customer"))
# Any authenticated user — no role restriction beyond authentication
require_any_role = Depends(get_current_user)


# ---------------------------------------------------------------------------
# Legacy alias — keeps old doctor-only endpoints working unchanged
# ---------------------------------------------------------------------------

async def require_doctor_dep(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Alias kept for backward-compat with existing doctor routes."""
    if current_user.get("role") not in ("doctor", "hospital_manager", "super_admin"):
        logger.warning(
            "Forbidden: user %s (role=%s) attempted doctor-only action",
            current_user.get("email"),
            current_user.get("role"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    return current_user


async def require_customer_dep(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current_user.get("role") not in ("customer", "patient"):  # accept legacy "patient" too
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    return current_user
