import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import case

from app.db import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.playlist import Playlist
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.models.user import User
from app.schemas.listening import ListeningEventCreate
from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistRename,
    PlaylistResponse,
    PlaylistTrackCreate,
)
from app.schemas.track import TrackResponse
from app.services.listening_service import record_listening_event
from app.services.playlists import ensure_liked_songs_playlist
from app.services.recommendations.playlist_recommender import (
    get_playlist_recommendations_for_playlist,
)

router = APIRouter()

PLAYLIST_ARTWORK_DIR = "data/uploads/playlist_artwork"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _get_user_playlist_or_404(db: Session, playlist_id: int, user_id: int) -> Playlist:
    playlist = (
        db.query(Playlist)
        .filter(
            Playlist.id == playlist_id,
            Playlist.user_id == user_id,
        )
        .first()
    )

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    return playlist


def _parse_exclude_track_ids(exclude_track_ids: str | None) -> list[int]:
    if not exclude_track_ids:
        return []

    parsed_ids: list[int] = []

    for raw_value in exclude_track_ids.split(","):
        value = raw_value.strip()
        if not value:
            continue

        try:
            parsed_ids.append(int(value))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid exclude_track_ids value: {value}",
            ) from exc

    return list(dict.fromkeys(parsed_ids))


@router.get("/playlists", response_model=list[PlaylistResponse], tags=["playlists"])
def list_playlists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_liked_songs_playlist(db, current_user.id)

    playlists = (
        db.query(Playlist)
        .filter(Playlist.user_id == current_user.id)
        .order_by(
            case(
                (Playlist.system_key.like("liked_songs:%"), 0),
                else_=1,
            ),
            Playlist.name.asc(),
        )
        .all()
    )

    return playlists


@router.post("/playlists", response_model=PlaylistResponse, tags=["playlists"])
def create_playlist(
    payload: PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (
        db.query(Playlist)
        .filter(
            Playlist.user_id == current_user.id,
            Playlist.name == payload.name,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Playlist already exists")

    playlist = Playlist(
        user_id=current_user.id,
        name=payload.name,
    )

    db.add(playlist)
    db.commit()
    db.refresh(playlist)

    return playlist


@router.get("/playlists/liked-songs", response_model=PlaylistResponse, tags=["playlists"])
def get_liked_songs_playlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ensure_liked_songs_playlist(db, current_user.id)


@router.get("/playlists/liked-songs/tracks/{track_id}", tags=["playlists"])
def is_track_in_liked_songs(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = ensure_liked_songs_playlist(db, current_user.id)

    playlist_track = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.track_id == track_id,
        )
        .first()
    )

    return {"liked": playlist_track is not None}


@router.post("/playlists/liked-songs/tracks", tags=["playlists"])
def add_track_to_liked_songs(
    payload: PlaylistTrackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = ensure_liked_songs_playlist(db, current_user.id)

    track = db.query(Track).filter(Track.id == payload.track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    existing_playlist_track = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.track_id == payload.track_id,
        )
        .first()
    )

    if existing_playlist_track:
        return {"liked": True}

    last_item = (
        db.query(PlaylistTrack)
        .filter(PlaylistTrack.playlist_id == playlist.id)
        .order_by(PlaylistTrack.position.desc())
        .first()
    )

    next_position = 0 if last_item is None else last_item.position + 1

    playlist_track = PlaylistTrack(
        playlist_id=playlist.id,
        track_id=payload.track_id,
        position=next_position,
    )

    db.add(playlist_track)
    db.flush()

    record_listening_event(
        db,
        ListeningEventCreate(
            track_id=payload.track_id,
            event_type="liked",
            source_type="playlist",
            source_id=playlist.id,
            position_seconds=None,
            duration_seconds=None,
            session_id=None,
        ),
        current_user.id,
    )

    return {"liked": True}


@router.delete("/playlists/liked-songs/tracks/{track_id}", tags=["playlists"])
def remove_track_from_liked_songs(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = ensure_liked_songs_playlist(db, current_user.id)

    playlist_track = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.track_id == track_id,
        )
        .order_by(PlaylistTrack.position.asc())
        .first()
    )

    if not playlist_track:
        return {"liked": False}

    removed_position = playlist_track.position

    db.delete(playlist_track)

    remaining_items = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.position > removed_position,
        )
        .order_by(PlaylistTrack.position.asc())
        .all()
    )

    for item in remaining_items:
        item.position -= 1

    record_listening_event(
        db,
        ListeningEventCreate(
            track_id=track_id,
            event_type="unliked",
            source_type="playlist",
            source_id=playlist.id,
            position_seconds=None,
            duration_seconds=None,
            session_id=None,
        ),
        current_user.id,
    )

    return {"liked": False}


@router.post("/playlists/{playlist_id}/artwork", response_model=PlaylistResponse, tags=["playlists"])
def upload_playlist_artwork(
    playlist_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    playlist = _get_user_playlist_or_404(db, playlist_id, current_user.id)

    if playlist.system_key:
        raise HTTPException(status_code=400, detail="System playlist artwork cannot be changed")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    os.makedirs(PLAYLIST_ARTWORK_DIR, exist_ok=True)

    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        extension = ".png"

    filename = f"{uuid4().hex}{extension}"
    file_path = os.path.join(PLAYLIST_ARTWORK_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if playlist.artwork_path:
        old_filename = os.path.basename(playlist.artwork_path)
        old_file_path = os.path.join(PLAYLIST_ARTWORK_DIR, old_filename)

        if os.path.exists(old_file_path):
            try:
                os.remove(old_file_path)
            except OSError:
                pass

    playlist.artwork_path = f"/uploads/playlist_artwork/{filename}"
    db.commit()
    db.refresh(playlist)

    return playlist


@router.post("/playlists/{playlist_id}/tracks", tags=["playlists"])
def add_track_to_playlist(
    playlist_id: int,
    payload: PlaylistTrackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = _get_user_playlist_or_404(db, playlist_id, current_user.id)

    track = db.query(Track).filter(Track.id == payload.track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    existing_playlist_track = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id == payload.track_id,
        )
        .first()
    )

    if existing_playlist_track:
        raise HTTPException(status_code=400, detail="Track already exists in playlist")

    last_item = (
        db.query(PlaylistTrack)
        .filter(PlaylistTrack.playlist_id == playlist_id)
        .order_by(PlaylistTrack.position.desc())
        .first()
    )

    next_position = 0 if last_item is None else last_item.position + 1

    playlist_track = PlaylistTrack(
        playlist_id=playlist_id,
        track_id=payload.track_id,
        position=next_position,
    )

    db.add(playlist_track)
    db.flush()

    record_listening_event(
        db,
        ListeningEventCreate(
            track_id=payload.track_id,
            event_type="playlist_added",
            source_type="playlist",
            source_id=playlist.id,
            position_seconds=None,
            duration_seconds=None,
            session_id=None,
        ),
        current_user.id,
    )

    db.refresh(playlist_track)

    return {
        "message": "Track added to playlist",
        "playlist_id": playlist_id,
        "track_id": payload.track_id,
        "position": next_position,
    }


@router.get(
    "/playlists/{playlist_id}/tracks",
    response_model=list[TrackResponse],
    tags=["playlists"],
)
def get_playlist_tracks(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = _get_user_playlist_or_404(db, playlist_id, current_user.id)

    playlist_tracks = (
        db.query(PlaylistTrack)
        .filter(PlaylistTrack.playlist_id == playlist.id)
        .order_by(PlaylistTrack.position.asc())
        .all()
    )

    return [playlist_track.track for playlist_track in playlist_tracks]


@router.get(
    "/playlists/{playlist_id}/recommendations",
    tags=["playlists"],
)
def get_playlist_recommendations(
    playlist_id: int,
    debug: bool = False,
    refresh: int = 0,
    limit: int = 20,
    exclude_track_ids: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = _get_user_playlist_or_404(db, playlist_id, current_user.id)
    parsed_exclude_track_ids = _parse_exclude_track_ids(exclude_track_ids)

    return get_playlist_recommendations_for_playlist(
        db=db,
        playlist_id=playlist.id,
        debug=debug,
        refresh=refresh,
        limit=limit,
        exclude_track_ids=parsed_exclude_track_ids,
    )


@router.delete("/playlists/{playlist_id}/tracks/{track_id}", tags=["playlists"])
def remove_track_from_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = _get_user_playlist_or_404(db, playlist_id, current_user.id)

    playlist_track = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.track_id == track_id,
        )
        .order_by(PlaylistTrack.position.asc())
        .first()
    )

    if not playlist_track:
        raise HTTPException(status_code=404, detail="Track not found in playlist")

    removed_position = playlist_track.position

    db.delete(playlist_track)

    remaining_items = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.position > removed_position,
        )
        .order_by(PlaylistTrack.position.asc())
        .all()
    )

    for item in remaining_items:
        item.position -= 1

    record_listening_event(
        db,
        ListeningEventCreate(
            track_id=track_id,
            event_type="playlist_removed",
            source_type="playlist",
            source_id=playlist.id,
            position_seconds=None,
            duration_seconds=None,
            session_id=None,
        ),
        current_user.id,
    )

    return {
        "message": "Track removed from playlist",
        "playlist_id": playlist_id,
        "track_id": track_id,
    }


@router.delete("/playlists/{playlist_id}", tags=["playlists"])
def delete_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = _get_user_playlist_or_404(db, playlist_id, current_user.id)

    if playlist.is_system:
        raise HTTPException(status_code=400, detail="System playlists cannot be deleted")

    db.delete(playlist)
    db.commit()

    return {
        "message": "Playlist deleted",
        "playlist_id": playlist_id,
    }


@router.patch("/playlists/{playlist_id}", response_model=PlaylistResponse, tags=["playlists"])
def rename_playlist(
    playlist_id: int,
    payload: PlaylistRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = _get_user_playlist_or_404(db, playlist_id, current_user.id)

    if playlist.is_system:
        raise HTTPException(status_code=400, detail="System playlists cannot be renamed")

    existing = (
        db.query(Playlist)
        .filter(
            Playlist.user_id == current_user.id,
            Playlist.name == payload.name,
            Playlist.id != playlist_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Playlist already exists")

    playlist.name = payload.name
    db.commit()
    db.refresh(playlist)

    return playlist