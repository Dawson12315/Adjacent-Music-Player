import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.config import settings
from app.models.user import User


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def password_fingerprint(password_hash: str) -> str:
    """Short, non-reversible stamp of the credential a token was minted under.

    Carried in the token as "pwd" so changing a password (or resetting it via
    a recovery code) invalidates every session issued before the change. The
    bcrypt hash already contains a random salt, so this leaks nothing useful
    about the password itself.
    """
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


# bcrypt only reads the first 72 bytes of input; both functions truncate the
# same way so hashing and verification stay consistent for longer passwords.
def hash_password(password: str) -> str:
    return password_context.hash(password[:72])


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password[:72], password_hash)


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": expires_at,
        # Binds the session to the current password. Tokens minted before this
        # existed simply lack the claim and stay valid until they expire —
        # deploying this must not sign everybody out.
        "pwd": password_fingerprint(user.password_hash),
    }

    return jwt.encode(
        payload,
        settings.auth_secret_key,
        algorithm=settings.auth_algorithm,
    )


def set_session_cookie(response: Response, token: str) -> None:
    """The one place the session cookie's attributes are decided.

    The logout route's `delete_cookie` has to match these or some browsers
    keep the cookie.
    """
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


# How much of a session's life may pass before a request re-mints it. The
# cookie used to be minted only at sign-in and never renewed, so "stay signed
# in" ended a week after sign-in however much the app was used. Half of the
# window means a device in regular use never reaches the expiry, while one
# left alone for the whole window still has to sign in again.
SESSION_REFRESH_AFTER_RATIO = 0.5


def session_token_needs_refresh(payload: dict | None, *, now: datetime | None = None) -> bool:
    """Whether a valid session token is far enough through its life to re-mint.

    False for anything that is not a session: a stream token (which carries
    "purpose" and travels in URLs), a token with no subject, and one already
    expired — that one is rejected, never renewed.
    """
    if not payload or payload.get("purpose") or not payload.get("sub"):
        return False

    expires_at = payload.get("exp")

    if not expires_at:
        return False

    remaining = datetime.fromtimestamp(expires_at, tz=timezone.utc) - (
        now or datetime.now(timezone.utc)
    )

    if remaining <= timedelta(0):
        return False

    lifetime = timedelta(minutes=settings.access_token_expire_minutes)

    return remaining < lifetime * SESSION_REFRESH_AFTER_RATIO


def reissue_access_token(payload: dict) -> str:
    """The same session, dated from now.

    Every claim but the expiry is carried over, the password fingerprint
    included: a password changed elsewhere still ends this session, because
    the fingerprint is what `get_current_user` checks.
    """
    claims = {key: value for key, value in payload.items() if key != "exp"}
    claims["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    return jwt.encode(
        claims,
        settings.auth_secret_key,
        algorithm=settings.auth_algorithm,
    )


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[settings.auth_algorithm],
        )
    except jwt.PyJWTError:
        return None


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def admin_exists(db: Session) -> bool:
    return db.query(User).filter(User.role == "admin").first() is not None