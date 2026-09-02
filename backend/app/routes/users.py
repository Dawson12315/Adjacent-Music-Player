"""Admin user management — the multi-user surface.

Available only when the install actually is multi-user (running on Postgres):
on SQLite these endpoints 403 with an explanation instead of quietly letting a
single-writer database accumulate concurrent users.

Account creation is admin-hands-a-password: a generated temp password is
returned exactly once, stored only as a bcrypt hash, and the new user is made
to choose their own at first sign-in. No email, no invites — this is a
self-hosted app on a home network.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.schemas.users import (
    TempPasswordResponse,
    UserCreatedResponse,
    UserUpdateRequest,
    UserCreateRequest,
)
from app.schemas.auth import UserResponse
from app.services.auth import hash_password

router = APIRouter()

# Readable-aloud temp passwords: adjective-bird-9999. ~26M combinations,
# bcrypt-hashed at rest, single-use by policy (must_change_password).
_ADJECTIVES = (
    "quiet", "amber", "brisk", "calm", "dapper", "eager", "floaty", "gentle",
    "happy", "keen", "lively", "mellow", "nimble", "plucky", "rapid", "sunny",
    "tidy", "vivid", "witty", "zesty", "bold", "cosy", "dusky", "early",
    "fuzzy", "glossy", "humble", "jolly", "lucky", "misty", "noble", "proud",
)
_BIRDS = (
    "mallard", "teal", "pintail", "wigeon", "eider", "scoter", "gadwall",
    "shoveler", "pochard", "goldeneye", "merganser", "duckling", "drake",
    "loon", "grebe", "coot", "heron", "plover", "sandpiper", "curlew",
    "godwit", "avocet", "puffin", "gannet", "petrel", "fulmar", "skua",
    "tern", "kittiwake", "osprey", "harrier", "goshawk",
)


def generate_temp_password() -> str:
    adjective = secrets.choice(_ADJECTIVES)
    bird = secrets.choice(_BIRDS)
    number = secrets.randbelow(9000) + 1000
    return f"{adjective}-{bird}-{number}"


def require_multi_user():
    if engine.dialect.name != "postgresql":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User management requires multi-user mode — enable it in "
            "Settings → Server first.",
        )


def _active_admin_count(db: Session) -> int:
    return (
        db.query(User)
        .filter(User.role == "admin", User.is_active.is_(True))
        .count()
    )


@router.get("/users", response_model=list[UserResponse], tags=["users"])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    _multi_user: None = Depends(require_multi_user),
):
    return db.query(User).order_by(User.created_at, User.id).all()


@router.post(
    "/users",
    response_model=UserCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["users"],
)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    _multi_user: None = Depends(require_multi_user),
):
    username = payload.username.strip()

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    temp_password = generate_temp_password()

    user = User(
        username=username,
        password_hash=hash_password(temp_password),
        role=payload.role,
        is_active=True,
        must_change_password=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"user": user, "temp_password": temp_password}


@router.patch("/users/{user_id}", response_model=UserResponse, tags=["users"])
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    _multi_user: None = Depends(require_multi_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    demoting = payload.role == "user" and user.role == "admin"
    deactivating = payload.is_active is False and user.is_active

    if user.id == current_user.id and (demoting or deactivating):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote or deactivate your own account.",
        )

    if (demoting or deactivating) and user.role == "admin":
        if _active_admin_count(db) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This is the last active admin — promote someone else first.",
            )

    if payload.role is not None:
        user.role = payload.role

    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", tags=["users"])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    _multi_user: None = Depends(require_multi_user),
):
    """Permanently remove a profile and everything that is theirs.

    Deactivation is the reversible tool; this one erases. The shared library
    is untouched — what goes is the account plus its playlists, likes (their
    Ducking Good is just a playlist), listening history, per-track stats and
    playback state. The user_id foreign keys carry no DB-level cascade, so
    dependents are removed explicitly, ORM-side where relationship cascades
    (playlist → entries, session → queue) do the child cleanup.
    """
    from app.models.listening_event import ListeningEvent
    from app.models.playback_session import PlaybackSession
    from app.models.playlist import Playlist
    from app.models.track_user_stats import TrackUserStats

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    if user.role == "admin" and user.is_active and _active_admin_count(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This is the last active admin — promote someone else first.",
        )

    events_removed = (
        db.query(ListeningEvent)
        .filter(ListeningEvent.user_id == user.id)
        .delete(synchronize_session=False)
    )
    stats_removed = (
        db.query(TrackUserStats)
        .filter(TrackUserStats.user_id == user.id)
        .delete(synchronize_session=False)
    )

    playlists = db.query(Playlist).filter(Playlist.user_id == user.id).all()
    for playlist in playlists:
        db.delete(playlist)

    playback_session = (
        db.query(PlaybackSession).filter(PlaybackSession.user_id == user.id).first()
    )
    if playback_session:
        db.delete(playback_session)

    # No relationship is mapped between User and these rows, so the unit of
    # work won't order the deletes on its own — flush the dependents before
    # the user row or Postgres raises on the FK.
    db.flush()

    username = user.username
    db.delete(user)
    db.commit()

    return {
        "deleted": True,
        "username": username,
        "removed": {
            "playlists": len(playlists),
            "listening_events": events_removed,
            "track_stats": stats_removed,
        },
    }


@router.post(
    "/users/{user_id}/reset-password",
    response_model=TempPasswordResponse,
    tags=["users"],
)
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    _multi_user: None = Depends(require_multi_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = generate_temp_password()
    user.password_hash = hash_password(temp_password)
    user.must_change_password = True

    db.commit()

    return {"temp_password": temp_password}
