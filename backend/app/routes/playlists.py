from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.playlist import Playlist
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.schemas.playlist import PlaylistCreate, PlaylistResponse, PlaylistTrackCreate
from app.schemas.track import TrackResponse

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

    existing_playlist_track = (
        db.query(PlaylistTrack)
        .filter(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id == payload.track_id
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