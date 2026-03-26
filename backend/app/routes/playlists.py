from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.playlist import Playlist
from app.schemas.playlist import PlaylistCreate, PlaylistResponse

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