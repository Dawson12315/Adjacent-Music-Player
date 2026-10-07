import hashlib
import hmac
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

from app.services.timezones import normalize_zone_name
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
    PreferencesUpdateRequest,
)
from app.services.auth import (
    admin_exists,
    create_access_token,
    get_user_by_username,
    hash_password,
    set_session_cookie,
    verify_password,
)
from app.services.rate_limit import (
    login_limiter,
    recovery_limiter,
    username_login_limiter,
    username_recovery_limiter,
)

logger = logging.getLogger(__name__)

# A bcrypt hash of nothing anyone can sign in with. Verified against when the
# username does not exist, so a wrong password costs the same 200 ms whether
# or not the account is real — the difference was a 200× timing oracle for
# usernames, measurable over the internet.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_hex(16))

router = APIRouter(tags=["auth"])


def set_auth_cookie(response: Response, token: str):
    # The attributes live with the token helpers, because the middleware that
    # renews a session mid-use has to write exactly the same cookie.
    set_session_cookie(response, token)


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
    return [secrets.token_hex(5).upper() for _ in range(count)]


def _recovery_code_digest(code: str) -> str:
    """A keyed hash, not bcrypt.

    Recovery codes are random 40-bit values, so the slow hash that protects
    guessable passwords buys nothing here — and ten bcrypt verifications per
    unauthenticated request made the endpoint a two-second CPU amplifier.
    HMAC with the server secret is constant-time and a thousand times cheaper.
    """
    return hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_recovery_codes(codes: list[str]) -> str:
    return json.dumps([_recovery_code_digest(code) for code in codes])


def _recovery_code_matches(code: str, stored: str) -> bool:
    # Codes issued before the HMAC scheme are bcrypt hashes; they keep working
    # until regenerated.
    if stored.startswith("$2"):
        return verify_password(code, stored)

    return hmac.compare_digest(_recovery_code_digest(code), stored)


def verify_and_consume_recovery_code(user: User, recovery_code: str) -> bool:
    if not user.recovery_codes_hashes:
        return False

    code = recovery_code.strip().upper()

    try:
        hashes = json.loads(user.recovery_codes_hashes)
    except json.JSONDecodeError:
        return False

    matched_index = None

    for index, code_hash in enumerate(hashes):
        if _recovery_code_matches(code, code_hash):
            matched_index = index
            break

    if matched_index is None:
        return False

    user.recovery_codes_hashes = json.dumps(
        [code_hash for index, code_hash in enumerate(hashes) if index != matched_index]
    )

    return True

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

    name_key = username_key(payload.username)

    user = get_user_by_username(db, payload.username.strip())

    # Verify against a dummy hash when the account does not exist, so the
    # request costs the same either way.
    password_ok = verify_password(
        payload.password,
        user.password_hash if user else DUMMY_PASSWORD_HASH,
    )

    if not user or not password_ok:
        login_limiter.record_failure(limiter_key)
        username_login_limiter.record_failure(name_key)

        # Second tier: survives an attacker rotating source addresses, and
        # covers the case where a misconfigured proxy makes every client share
        # one key. Checked after the password rather than before, so it only
        # ever slows *wrong* guesses: the account's owner, typing the right
        # password, is never the one locked out by somebody else's attempts.
        retry_after = username_login_limiter.retry_after_seconds(name_key)

        if retry_after:
            logger.warning(
                "Login for %r refused: too many failed attempts across clients "
                "(latest from %s)",
                payload.username.strip(),
                request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )

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
        # A wrong current password is a mistake in the form, not a dead
        # session — the cookie that authenticated this request is fine. A 401
        # here made the clients treat it as an expiry and sign the person
        # out, hiding the one message that would have helped.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    new_username = payload.username.strip() if payload.username else current_user.username

    if new_username != current_user.username:
        existing_user = get_user_by_username(db, new_username)
        if existing_user and existing_user.id != current_user.id:
            # The same words as any other refusal of the name: "already
            # exists" let any signed-in user walk the user table.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That username is not available",
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


@router.patch("/auth/me/preferences", response_model=UserResponse, tags=["auth"])
def update_preferences(
    payload: PreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A preference, not a credential: no password asked.

    The account route above re-fingerprints the session and insists on the
    current password, which is right for a username or password and wrong
    for a time zone. Allowed to an account still owing a password, too.
    """
    if payload.timezone is None or not payload.timezone.strip():
        current_user.timezone = None
    else:
        zone = normalize_zone_name(payload.timezone)
        if zone is None:
            raise HTTPException(status_code=422, detail=f"Unknown time zone: {payload.timezone}")
        current_user.timezone = zone

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/auth/recover-password")
def recover_password(
    payload: PasswordRecoveryRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    limiter_key = rate_limit_key(request, payload.username)
    name_key = username_key(payload.username)
    raise_if_rate_limited(recovery_limiter, limiter_key)
    raise_if_rate_limited(username_recovery_limiter, name_key)

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match",
        )

    user = get_user_by_username(db, payload.username.strip())

    if not user or not user.is_active or not user.recovery_codes_hashes:
        # One dummy verification, so an account with no codes (or none at
        # all) answers in the same time as one with them.
        verify_password(payload.recovery_code, DUMMY_PASSWORD_HASH)
        recovery_limiter.record_failure(limiter_key)
        username_recovery_limiter.record_failure(name_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or recovery code",
        )

    if not verify_and_consume_recovery_code(user, payload.recovery_code):
        recovery_limiter.record_failure(limiter_key)
        username_recovery_limiter.record_failure(name_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or recovery code",
        )

    recovery_limiter.record_success(limiter_key)
    username_recovery_limiter.record_success(name_key)

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