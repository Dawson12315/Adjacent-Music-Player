from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    AdminSetupRequest,
    AuthResponse,
    LoginRequest,
    SetupStatusResponse,
    UserResponse,
)
from app.services.auth import (
    admin_exists,
    create_access_token,
    get_user_by_username,
    hash_password,
    verify_password,
)


router = APIRouter(tags=["auth"])


def set_auth_cookie(response: Response, token: str):
    is_production = settings.app_env.lower() == "production"

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.get("/auth/setup-status", response_model=SetupStatusResponse)
def get_setup_status(db: Session = Depends(get_db)):
    return {"admin_exists": admin_exists(db)}


@router.post("/auth/setup-admin", response_model=AuthResponse)
def setup_admin(
    payload: AdminSetupRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    if admin_exists(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account already exists",
        )

    existing_user = get_user_by_username(db, payload.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role="admin",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user)
    set_auth_cookie(response, token)

    return {"user": user}


@router.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(db, payload.username.strip())

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    token = create_access_token(user)
    set_auth_cookie(response, token)

    return {"user": user}


@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
    )

    return {"message": "Logged out"}