from datetime import datetime, timedelta, timezone
import os

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from database.db import (
    create_login_attempt,
    create_user,
    get_login_attempts_collection,
    get_user_by_email,
    get_users_collection,
)
from model.user import (
    AuthResponse,
    PasswordChangeRequest,
    PasswordVerifyRequest,
    PasswordVerifyResponse,
    UserData,
    UserLogin,
    UserPublic,
    UserSignup,
)
from services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)


router = APIRouter(tags=["auth"])


MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOGIN_WINDOW_MINUTES = int(os.getenv("LOGIN_WINDOW_MINUTES", "15"))


def _recent_failed_login_attempts(email: str) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    return get_login_attempts_collection().count_documents(
        {
            "email": email,
            "success": False,
            "created_at": {"$gte": cutoff},
        }
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED, summary="Signup")
def signup(payload: UserSignup) -> AuthResponse:
    email = payload.email.strip().lower()
    try:
        if get_user_by_email(email) is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists",
            )

        salt_hex, password_hash_hex = hash_password(payload.password)
        user = create_user(payload.name.strip(), email, salt_hex, password_hash_hex)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        ) from exc
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not connected",
        ) from exc
    token = create_access_token(user)
    return AuthResponse(
        message="User registered successfully",
        access_token=token,
        user=UserPublic(id=user["id"], name=user["name"], email=user["email"]),
    )


@router.post("/login", response_model=AuthResponse, summary="Login")
def login(payload: UserLogin) -> AuthResponse:
    email = payload.email.strip().lower()
    try:
        user = get_user_by_email(email)
        if user and _recent_failed_login_attempts(email) >= MAX_LOGIN_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later.",
            )

        if not user or not verify_password(payload.password, user["salt"], user["password_hash"]):
            create_login_attempt(
                email=email,
                success=False,
                user_id=user["id"] if user else None,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        create_login_attempt(email=email, success=True, user_id=user["id"])
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not connected",
        ) from exc
    token = create_access_token(user)
    return AuthResponse(
        message="Login successful",
        access_token=token,
        user=UserPublic(id=user["id"], name=user["name"], email=user["email"]),
    )


@router.get("/me", response_model=UserData, summary="Current user")
def me(current_user: dict[str, object] = Depends(get_current_user)) -> UserData:
    return UserData(name=current_user["name"], email=current_user["email"])


@router.post("/verify-password", response_model=PasswordVerifyResponse, summary="Verify password")
def verify_user_password(
    payload: PasswordVerifyRequest,
    current_user: dict[str, object] = Depends(get_current_user),
) -> PasswordVerifyResponse:
    is_valid = verify_password(payload.password, current_user["salt"], current_user["password_hash"])
    return PasswordVerifyResponse(
        message="Password verified" if is_valid else "Password does not match",
        is_valid=is_valid,
    )


@router.post("/change-password", summary="Change password")
def change_user_password(
    payload: PasswordChangeRequest,
    current_user: dict[str, object] = Depends(get_current_user),
) -> dict[str, str]:
    if not verify_password(
        payload.current_password,
        current_user["salt"],
        current_user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    if verify_password(
        payload.new_password,
        current_user["salt"],
        current_user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    salt_hex, password_hash_hex = hash_password(payload.new_password)
    result = get_users_collection().update_one(
        {"email": current_user["email"]},
        {"$set": {"salt": salt_hex, "password_hash": password_hash_hex}},
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"message": "Password updated successfully. Please log in again."}
