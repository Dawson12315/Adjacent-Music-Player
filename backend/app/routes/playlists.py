from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.playlist import Playlist
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.schemas.playlist import PlaylistCreate, PlaylistResponse, PlaylistTrackCreate

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