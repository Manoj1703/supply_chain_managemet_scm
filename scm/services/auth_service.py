from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac
from os import urandom
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError

from database.db import get_user_by_email


JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or urandom(16)
    hashed = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return salt.hex(), hashed.hex()


def verify_password(password: str, salt_hex: str, password_hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    _, computed_hash = hash_password(password, salt)
    return hmac.compare_digest(computed_hash, password_hash_hex)


def _password_fingerprint(user: dict[str, Any]) -> str:
    raw = f"{user['salt']}:{user['password_hash']}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_access_token(user: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["email"],
        "user_id": user["id"],
        "name": user["name"],
        "pwd": _password_fingerprint(user),
        "iat": now,
        "exp": now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
        )

    payload = decode_access_token(credentials.credentials)
    user = get_user_by_email(payload["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    token_fingerprint = payload.get("pwd")
    if token_fingerprint != _password_fingerprint(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is no longer valid",
        )

    return user
