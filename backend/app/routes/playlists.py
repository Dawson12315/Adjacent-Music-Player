import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.playlist import Playlist
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistRename,
    PlaylistResponse,
    PlaylistTrackCreate,
)
from app.schemas.track import TrackResponse
from app.services.recommendations.playlist_recommender import (
    get_playlist_recommendations_for_playlist,
)


router = APIRouter()


@router.get("/playlists", response_model=list[PlaylistResponse], tags=["playlists"])
def list_playlists(db: Session = Depends(get_db)):
    playlists = db.query(Playlist).order_by(Playlist.name.asc()).all()
    return playlists


@router.post("/playlists", response_model=PlaylistResponse, tags=["playlists"])
def create_playlist(payload: PlaylistCreate, db: Session = Depends(get_db)):
    existing = db.query(Playlist).filter(Playlist.name == payload.name).first()

    if existing:
        raise HTTPException(status_code=400, detail="Playlist already exists")

    playlist = Playlist(name=payload.name)

    db.add(playlist)
    db.commit()
    db.refresh(playlist)

    return playlist


def _get_liked_songs_playlist(db: Session) -> Playlist:
    playlist = (
        db.query(Playlist)
        .filter(Playlist.system_key == "liked_songs")
        .first()
    )

    if not playlist:
        raise HTTPException(status_code=404, detail="Liked Songs playlist not found")

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


@router.get("/playlists/liked-songs", response_model=PlaylistResponse, tags=["playlists"])
def get_liked_songs_playlist(db: Session = Depends(get_db)):
    playlist = (
        db.query(Playlist)
        .filter(Playlist.system_key == "liked_songs")
        .first()
    )

    if not playlist:
        raise HTTPException(status_code=404, detail="Liked Songs playlist not found")

    return playlist


@router.get("/playlists/liked-songs/tracks/{track_id}", tags=["playlists"])
def is_track_in_liked_songs(track_id: int, db: Session = Depends(get_db)):
    playlist = _get_liked_songs_playlist(db)

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
def add_track_to_liked_songs(payload: PlaylistTrackCreate, db: Session = Depends(get_db)):
    playlist = _get_liked_songs_playlist(db)

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
    db.commit()

    return {"liked": True}


@router.delete("/playlists/liked-songs/tracks/{track_id}", tags=["playlists"])
def remove_track_from_liked_songs(track_id: int, db: Session = Depends(get_db)):
    playlist = _get_liked_songs_playlist(db)

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
    db.commit()

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

    db.commit()

    return {"liked": False}


@router.post("/playlists/{playlist_id}/artwork", response_model=PlaylistResponse, tags=["playlists"])
def upload_playlist_artwork(
    playlist_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    if playlist.system_key == "liked_songs":
        raise HTTPException(status_code=400, detail="Liked Songs artwork cannot be changed")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    upload_dir = "app/uploads/playlist_artwork"
    os.makedirs(upload_dir, exist_ok=True)

    extension = os.path.splitext(file.filename or "")[1].lower() or ".png"
    filename = f"{uuid4().hex}{extension}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if playlist.artwork_path:
        old_path = playlist.artwork_path.lstrip("/")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
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
):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

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
    db.commit()
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
def get_playlist_tracks(playlist_id: int, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    playlist_tracks = (
        db.query(PlaylistTrack)
        .filter(PlaylistTrack.playlist_id == playlist_id)
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
):
    parsed_exclude_track_ids = _parse_exclude_track_ids(exclude_track_ids)

    return get_playlist_recommendations_for_playlist(
        db=db,
        playlist_id=playlist_id,
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
):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    playlist_track = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id == track_id,
        )
        .order_by(PlaylistTrack.position.asc())
        .first()
    )

    if not playlist_track:
        raise HTTPException(status_code=404, detail="Track not found in playlist")

    removed_position = playlist_track.position

    db.delete(playlist_track)
    db.commit()

    remaining_items = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.position > removed_position,
        )
        .order_by(PlaylistTrack.position.asc())
        .all()
    )

    for item in remaining_items:
        item.position -= 1

    db.commit()

    return {
        "message": "Track removed from playlist",
        "playlist_id": playlist_id,
        "track_id": track_id,
    }


@router.delete("/playlists/{playlist_id}", tags=["playlists"])
def delete_playlist(playlist_id: int, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

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
):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    if playlist.is_system:
        raise HTTPException(status_code=400, detail="System playlists cannot be renamed")

    existing = (
        db.query(Playlist)
        .filter(Playlist.name == payload.name, Playlist.id != playlist_id)
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Playlist already exists")

    playlist.name = payload.name
    db.commit()
    db.refresh(playlist)

    return playlist