import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.album_artwork import AlbumArtwork
from app.models.track import Track
from app.models.user import User

from app.models.artist_artwork import ArtistArtwork
from app.schemas.track import TrackResponse
from app.utils.artist_normalization import normalize_artist_name

router = APIRouter()

ALBUM_ARTWORK_DIR = "data/uploads/albums"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def normalize_album_name(album_name: str) -> str:
    return " ".join((album_name or "").strip().casefold().split())


@router.get("/albums", tags=["albums"])
def list_albums(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    albums = (
        db.query(Track.album)
        .filter(Track.album.isnot(None))
        .group_by(Track.album)
        .order_by(func.lower(Track.album))
        .all()
    )
    return [album[0] for album in albums if album[0]]

def build_mobile_album_track_response(track: Track, db: Session) -> TrackResponse:
    album_key = normalize_album_name(track.album)
    artist_key = normalize_artist_name(track.artist)

    album_artwork = db.query(AlbumArtwork).filter(
        AlbumArtwork.album_key == album_key
    ).first()

    artist_artwork = db.query(ArtistArtwork).filter(
        ArtistArtwork.artist_key == artist_key
    ).first()

    album_artwork_path = album_artwork.artwork_path if album_artwork else None
    artist_artwork_path = artist_artwork.artwork_path if artist_artwork else None

    return TrackResponse(
        id=track.id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        genre=track.genre,
        genres=[item.genre for item in track.track_genres],
        artists=[item.artist_name for item in track.track_artists],
        file_path=track.file_path,
        artwork_path=album_artwork_path,
        album_artwork_path=album_artwork_path,
        artist_artwork_path=artist_artwork_path,
        raw_title=track.raw_title,
        raw_artist=track.raw_artist,
        raw_album=track.raw_album,
        raw_genre=track.raw_genre,
        musicbrainz_recording_id=track.musicbrainz_recording_id,
        lastfm_tags_enriched=track.lastfm_tags_enriched,
    )


@router.get("/mobile/albums", tags=["mobile"])
def list_mobile_albums(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    album_rows = (
        db.query(
            Track.album.label("album"),
            func.min(Track.artist).label("artist"),
            func.count(Track.id).label("track_count"),
        )
        .filter(Track.album.isnot(None))
        .group_by(Track.album)
        .order_by(func.lower(Track.album))
        .all()
    )

    album_keys = [normalize_album_name(row.album) for row in album_rows if row.album]
    artwork_rows = (
        db.query(AlbumArtwork)
        .filter(AlbumArtwork.album_key.in_(album_keys))
        .all()
        if album_keys
        else []
    )
    artwork_by_key = {artwork.album_key: artwork.artwork_path for artwork in artwork_rows}

    return [
        {
            "name": row.album,
            "album": row.album,
            "artist": row.artist or "Unknown Artist",
            "trackCount": row.track_count,
            "track_count": row.track_count,
            "artwork_path": artwork_by_key.get(normalize_album_name(row.album)),
            "album_artwork_path": artwork_by_key.get(normalize_album_name(row.album)),
        }
        for row in album_rows
        if row.album
    ]


@router.get("/mobile/albums/{album_name:path}/tracks", response_model=list[TrackResponse], tags=["mobile"])
def get_mobile_album_tracks(
    album_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(func.lower(Track.album) == album_name.casefold())
        .order_by(Track.title.asc())
        .all()
    )

    return [build_mobile_album_track_response(track, db) for track in tracks]

@router.get("/albums/{album_name:path}/artwork", tags=["albums"])
def get_album_artwork(
    album_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.post("/albums/{album_name:path}/artwork", tags=["albums"])
def upload_album_artwork(
    album_name: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
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