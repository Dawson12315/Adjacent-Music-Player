import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.album_artwork import AlbumArtwork
from app.models.track import Track

router = APIRouter()

ALBUM_ARTWORK_DIR = "data/uploads/albums"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def normalize_album_name(album_name: str) -> str:
    return " ".join((album_name or "").strip().casefold().split())


@router.get("/albums", tags=["albums"])
def list_albums(db: Session = Depends(get_db)):
    albums = (
        db.query(Track.album)
        .filter(Track.album.isnot(None))
        .group_by(Track.album)
        .order_by(func.lower(Track.album))
        .all()
    )
    return [album[0] for album in albums if album[0]]


@router.get("/albums/{album_name}/artwork", tags=["albums"])
def get_album_artwork(album_name: str, db: Session = Depends(get_db)):
    album_key = normalize_album_name(album_name)

    artwork = (
        db.query(AlbumArtwork)
        .filter(AlbumArtwork.album_key == album_key)
        .first()
    )

    return {
        "album_name": album_name,
        "album_key": album_key,
        "artwork_path": artwork.artwork_path if artwork else None,
    }


@router.post("/albums/{album_name}/artwork", tags=["albums"])
def upload_album_artwork(
    album_name: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    album_key = normalize_album_name(album_name)

    if not album_key:
        raise HTTPException(status_code=400, detail="Invalid album name")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    os.makedirs(ALBUM_ARTWORK_DIR, exist_ok=True)

    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        extension = ".jpg"

    filename = f"{uuid4().hex}{extension}"
    file_path = os.path.join(ALBUM_ARTWORK_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    artwork_path = f"/uploads/albums/{filename}"

    artwork = (
        db.query(AlbumArtwork)
        .filter(AlbumArtwork.album_key == album_key)
        .first()
    )

    if artwork:
        if artwork.artwork_path:
            old_filename = os.path.basename(artwork.artwork_path)
            old_file_path = os.path.join(ALBUM_ARTWORK_DIR, old_filename)

            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except OSError:
                    pass

        artwork.album_name = album_name
        artwork.artwork_path = artwork_path
    else:
        artwork = AlbumArtwork(
            album_name=album_name,
            album_key=album_key,
            artwork_path=artwork_path,
        )
        db.add(artwork)

    db.commit()
    db.refresh(artwork)

    return {
        "album_name": artwork.album_name,
        "album_key": artwork.album_key,
        "artwork_path": artwork.artwork_path,
    }