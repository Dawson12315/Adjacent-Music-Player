import json
import logging
import secrets
from datetime import datetime, timedelta

# How long an admin-issued one-time password stays usable before the admin
# must re-issue it. Long enough to hand someone a password in the evening and
# have them sign in the next day.
TEMP_PASSWORD_TTL_HOURS = 48


from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    AccountUpdateRequest,
    AdminSetupRequest,
    AuthResponse,
    LoginRequest,
    SetupStatusResponse,
    UserResponse,
    PasswordRecoveryRequest,
    RecoveryCodesResponse,
)
from app.services.auth import (
    admin_exists,
    create_access_token,
    get_user_by_username,
    hash_password,
    verify_password,
)
from app.services.rate_limit import (
    login_limiter,
    recovery_limiter,
    username_login_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def rate_limit_key(request: Request, username: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{username.strip().lower()}"


def username_key(username: str) -> str:
    """Key for the per-username ceiling, which ignores the client address."""
    return username.strip().lower()


def raise_if_rate_limited(limiter, key: str):
    retry_after = limiter.retry_after_seconds(key)

    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

def generate_recovery_codes(count: int = 10) -> list[str]:
    return [secrets.token_hex(4).upper() for _ in range(count)]


def hash_recovery_codes(codes: list[str]) -> str:
    return json.dumps([hash_password(code) for code in codes])


def verify_and_consume_recovery_code(user: User, recovery_code: str) -> bool:
    if not user.recovery_codes_hashes:
        return False

    code = recovery_code.strip().upper()

    try:
        hashes = json.loads(user.recovery_codes_hashes)
    except json.JSONDecodeError:
        return False

    remaining_hashes = []
    matched = False

    for code_hash in hashes:
        if not matched and verify_password(code, code_hash):
            matched = True
            continue

        remaining_hashes.append(code_hash)

    if matched:
        user.recovery_codes_hashes = json.dumps(remaining_hashes)

    return matched

@router.get("/auth/setup-status", response_model=SetupStatusResponse)
def get_setup_status(db: Session = Depends(get_db)):
    return {
        "admin_exists": admin_exists(db),
        "setup_token_required": bool(settings.setup_token),
    }


@router.post("/auth/setup-admin", response_model=AuthResponse)
def setup_admin(
    payload: AdminSetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    username = payload.username.strip()

    if admin_exists(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account already exists",
        )

    # First-run setup is otherwise first-come-first-served: whoever reaches an
    # admin-less instance owns it. Harmless on a LAN, a race against scanners
    # once the app is on the internet. Setting SETUP_TOKEN closes that window;
    # leaving it unset preserves the original zero-config behaviour.
    if settings.setup_token:
        if not secrets.compare_digest(payload.setup_token or "", settings.setup_token):
            logger.warning(
                "Rejected setup-admin attempt from %s (bad or missing setup token)",
                request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A setup token is required to create the first admin account.",
            )

    existing_user = get_user_by_username(db, username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role="admin",
        is_active=True,
    )

    recovery_codes = generate_recovery_codes()
    user.recovery_codes_hashes = hash_recovery_codes(recovery_codes)
    
    db.add(user)
    db.commit()
    db.refresh(user)

    # A hijacked first-run is otherwise invisible; this is the one line that
    # tells the owner an admin was created and from where.
    logger.warning(
        "First-run admin account %r created from %s",
        user.username,
        request.client.host if request.client else "unknown",
    )

    token = create_access_token(user)
    set_auth_cookie(response, token)

    return {"user": user}


@router.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    limiter_key = rate_limit_key(request, payload.username)
    raise_if_rate_limited(login_limiter, limiter_key)

    # Second tier: survives an attacker rotating source addresses, and covers
    # the case where a misconfigured proxy makes every client share one key.
    name_key = username_key(payload.username)
    raise_if_rate_limited(username_login_limiter, name_key)

    user = get_user_by_username(db, payload.username.strip())

    if not user or not verify_password(payload.password, user.password_hash):
        login_limiter.record_failure(limiter_key)
        username_login_limiter.record_failure(name_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    # An admin-issued one-time password that was never redeemed is a standing
    # guessable credential. Past its lifetime the account needs a fresh one.
    if (
        user.must_change_password
        and user.temp_password_issued_at is not None
        and datetime.utcnow() - user.temp_password_issued_at
        > timedelta(hours=TEMP_PASSWORD_TTL_HOURS)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This one-time password has expired. Ask an admin to reset it."
            ),
        )

    login_limiter.record_success(limiter_key)
    username_login_limiter.record_success(name_key)

    token = create_access_token(user)
    set_auth_cookie(response, token)

    return {"user": user}


@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/auth/me", response_model=AuthResponse)
def update_me(
    payload: AccountUpdateRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    new_username = payload.username.strip() if payload.username else current_user.username

    if new_username != current_user.username:
        existing_user = get_user_by_username(db, new_username)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

        current_user.username = new_username

    if payload.new_password or payload.confirm_password:
        if not payload.new_password or not payload.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter and confirm the new password",
            )

        if payload.new_password != payload.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New passwords do not match",
            )

        current_user.password_hash = hash_password(payload.new_password)
        # A real password of their own choosing lifts the temp-password hold.
        current_user.must_change_password = False
        current_user.temp_password_issued_at = None

    db.commit()
    db.refresh(current_user)

    token = create_access_token(current_user)
    set_auth_cookie(response, token)

    return {"user": current_user}

@router.post("/auth/recovery-codes", response_model=RecoveryCodesResponse)
def regenerate_recovery_codes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recovery_codes = generate_recovery_codes()
    current_user.recovery_codes_hashes = hash_recovery_codes(recovery_codes)

    db.commit()

    return {"recovery_codes": recovery_codes}


@router.post("/auth/recover-password")
def recover_password(
    payload: PasswordRecoveryRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    limiter_key = rate_limit_key(request, payload.username)
    raise_if_rate_limited(recovery_limiter, limiter_key)

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match",
        )

    user = get_user_by_username(db, payload.username.strip())

    if not user or not user.is_active:
        recovery_limiter.record_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or recovery code",
        )

    if not verify_and_consume_recovery_code(user, payload.recovery_code):
        recovery_limiter.record_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or recovery code",
        )

    recovery_limiter.record_success(limiter_key)

    user.password_hash = hash_password(payload.new_password)
    # Recovering with a code is the user choosing their own password, so any
    # pending admin-issued temp password is spent. (Changing the hash also
    # invalidates every outstanding session via the token's "pwd" claim.)
    user.must_change_password = False
    user.temp_password_issued_at = None

    db.commit()

    return {"message": "Password reset successfully"}

@router.post("/auth/logout")
def logout(response: Response):
    # Attributes must match set_auth_cookie or some browsers keep the cookie.
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )

    return {"message": "Logged out"}