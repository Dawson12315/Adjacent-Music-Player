import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.artist_artwork import ArtistArtwork
from app.models.track_artist import TrackArtist
from app.utils.artist_normalization import normalize_artist_name

router = APIRouter()

ARTIST_ARTWORK_DIR = "uploads/artists"


@router.get("/artists", tags=["artists"])
def list_artists(db: Session = Depends(get_db)):
    artists = (
        db.query(TrackArtist.artist_name)
        .filter(TrackArtist.artist_name.isnot(None))
        .group_by(TrackArtist.artist_name)
        .order_by(func.lower(TrackArtist.artist_name))
        .all()
    )

    return [artist[0] for artist in artists if artist[0]]


@router.get("/artists/{artist_name}/artwork", tags=["artists"])
def get_artist_artwork(artist_name: str, db: Session = Depends(get_db)):
    artist_key = normalize_artist_name(artist_name)

    artwork = (
        db.query(ArtistArtwork)
        .filter(ArtistArtwork.artist_key == artist_key)
        .first()
    )

    return {
        "artist_name": artist_name,
        "artist_key": artist_key,
        "artwork_path": artwork.artwork_path if artwork else None,
    }


@router.post("/artists/{artist_name}/artwork", tags=["artists"])
def upload_artist_artwork(
    artist_name: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    artist_key = normalize_artist_name(artist_name)

    if not artist_key:
        raise HTTPException(status_code=400, detail="Invalid artist name")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    os.makedirs(ARTIST_ARTWORK_DIR, exist_ok=True)

    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".jpg"

    filename = f"{uuid4()}{extension}"
    file_path = os.path.join(ARTIST_ARTWORK_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    artwork_path = f"/{file_path}"

    artwork = (
        db.query(ArtistArtwork)
        .filter(ArtistArtwork.artist_key == artist_key)
        .first()
    )

    if artwork:
        artwork.artist_name = artist_name
        artwork.artwork_path = artwork_path
    else:
        artwork = ArtistArtwork(
            artist_name=artist_name,
            artist_key=artist_key,
            artwork_path=artwork_path,
        )
        db.add(artwork)

    db.commit()
    db.refresh(artwork)

    return {
        "artist_name": artwork.artist_name,
        "artist_key": artwork.artist_key,
        "artwork_path": artwork.artwork_path,
    }