from datetime import datetime, timedelta

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.user import User
from app.services.auth import (
    decode_access_token,
    get_user_by_id,
    password_fingerprint,
)


# What an account still holding an admin-issued one-time password may do:
# see itself, change the password, sign out, and nothing else. Everything the
# login-time checks enforced used to be bypassable by any client that did not
# implement the forced-change screen — the cookie worked for its full week.
PASSWORD_CHANGE_ALLOWED = {
    ("GET", "/api/auth/me"),
    ("PATCH", "/api/auth/me"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/recovery-codes"),
}

# Must match the login-time TTL in routes/auth.py.
TEMP_PASSWORD_TTL_HOURS = 48


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None, alias=settings.auth_cookie_name),
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(access_token)

    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    # Stream tokens are signed with the same key but are deliberately allowed
    # to travel in URLs (HLS playlists, query params), so they end up in proxy
    # logs and shared links. They carry a "purpose" claim; session tokens never
    # do. Without this check a leaked stream URL is a full API session for
    # whoever it was minted for — admin included.
    if payload.get("purpose"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    user = get_user_by_id(db, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive or missing",
        )

    # A password change or recovery reset re-fingerprints the credential, so
    # sessions minted under the old one stop working. Tokens predating this
    # feature carry no "pwd" claim and are accepted until they expire.
    token_fingerprint = payload.get("pwd")

    if token_fingerprint and token_fingerprint != password_fingerprint(
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — sign in again",
        )

    if user.must_change_password:
        issued_at = user.temp_password_issued_at

        if issued_at is not None and datetime.utcnow() - issued_at > timedelta(
            hours=TEMP_PASSWORD_TTL_HOURS
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This one-time password has expired. Ask an admin to reset it.",
            )

        if (request.method, request.url.path) not in PASSWORD_CHANGE_ALLOWED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Choose a password before using the app.",
                headers={"X-Adjacent-Code": "password_change_required"},
            )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user