from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.playlist import Playlist
from app.schemas.playlist import PlaylistResponse

router = APIRouter()


@router.get("/playlists", response_model=list[PlaylistResponse], tags=["playlists"])
def list_playlists(db: Session = Depends(get_db)):
    playlists = db.query(Playlist).order_by(Playlist.name.asc()).all()
    return playlists