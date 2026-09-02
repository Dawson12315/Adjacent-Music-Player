import hashlib
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

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


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[settings.auth_algorithm],
        )
    except JWTError:
        return None


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def admin_exists(db: Session) -> bool:
    return db.query(User).filter(User.role == "admin").first() is not None