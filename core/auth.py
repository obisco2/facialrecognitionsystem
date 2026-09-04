"""
JWT Authentication for AttendIQ.
Access token (15m) + Refresh token (7d) with hashed storage and RBAC helpers.
"""
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import Config

logger = logging.getLogger(__name__)
config = Config()

# Re-use DB lazily to avoid circular import at module load
def _db():
    from core.database import DatabaseManager
    # Use singleton db instance from backend if available
    try:
        from core.backend import db as backend_db
        return backend_db
    except Exception:
        return DatabaseManager(config.db_path)

security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def _get_secret(kind: str = "access") -> str:
    """Load secret from env/config.ini; fallback to generated dev secret with warning."""
    if kind == "refresh":
        env = config.get("Security", "JWT_REFRESH_SECRET", fallback=None)
        if env is None:
            import os
            env = os.getenv("JWT_REFRESH_SECRET")
        if env:
            return env
        # Derive refresh secret from access secret + salt to avoid identical keys
        access = _get_secret("access")
        return hashlib.sha256((access + "_refresh").encode()).hexdigest()
    # access
    sec = config.get("Security", "JWT_SECRET", fallback=None)
    if sec is None:
        import os
        sec = os.getenv("JWT_SECRET")
    if sec:
        return sec
    # Dev fallback — warn and use ephemeral
    logger.warning("JWT_SECRET not set — using ephemeral dev secret. Set JWT_SECRET in config.ini/.env for production.")
    return "dev-insecure-jwt-secret-change-me"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, username: str, role: str, full_name: str) -> str:
    exp = _now_utc() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "full_name": full_name,
        "type": "access",
        "iat": int(_now_utc().timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _get_secret("access"), algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    exp = _now_utc() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = secrets.token_hex(16)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": "refresh",
        "iat": int(_now_utc().timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, _get_secret("refresh"), algorithm=ALGORITHM)
    # Store hashed
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = exp.strftime("%Y-%m-%d %H:%M:%S")
    db = _db()
    try:
        with db._conn:
            db._conn.execute(
                "INSERT INTO refresh_tokens (user_id, token_hash, jti, expires_at) VALUES (?, ?, ?, ?)",
                (user_id, token_hash, jti, expires_at),
            )
    except Exception as e:
        logger.error("Failed to store refresh token: %s", e)
        raise HTTPException(status_code=500, detail="Failed to issue refresh token")
    return token


def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _get_secret("access"), algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def verify_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _get_secret("refresh"), algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        # Check DB presence (revocation)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        db = _db()
        row = db._conn.execute(
            "SELECT * FROM refresh_tokens WHERE token_hash = ? AND jti = ?",
            (token_hash, payload.get("jti")),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Refresh token revoked or not found")
        # Check DB expiry
        expires_at = row["expires_at"]
        try:
            exp_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if _now_utc() > exp_dt:
                # Cleanup
                with db._conn:
                    db._conn.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
                raise HTTPException(status_code=401, detail="Refresh token expired")
        except HTTPException:
            raise
        except Exception:
            pass
        return payload
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {e}")


def revoke_refresh_token(token: str):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db = _db()
    with db._conn:
        db._conn.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))


def revoke_all_user_tokens(user_id: int):
    db = _db()
    with db._conn:
        db._conn.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))


# --- FastAPI dependencies ---

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Dependency that returns user dict; raises 401 if missing/invalid."""
    # Allow token via Authorization header or httpOnly cookie (for browser)
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif request.cookies.get("access_token"):
        token = request.cookies.get("access_token")
    # Also check manual header (case for pywebview)
    if not token:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = verify_access_token(token)
    db = _db()
    user = db.get_user(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # Attach payload for downstream use
    user["_token_payload"] = payload
    return user


def require_roles(*roles: str):
    """Factory dependency that enforces role. Usage: Depends(require_roles('admin','lecturer'))"""
    def _checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
        return user
    return _checker


# Convenience wrappers
require_admin = require_roles("admin")
require_lecturer = require_roles("lecturer", "admin")
require_student = require_roles("student", "admin")
