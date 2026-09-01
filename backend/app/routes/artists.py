import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.album_artwork import AlbumArtwork
from app.models.artist_artwork import ArtistArtwork
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.user import User
from app.routes.albums import normalize_album_name
from app.schemas.track import TrackResponse
from app.utils.artist_normalization import normalize_artist_name

router = APIRouter()

ARTIST_ARTWORK_DIR = "data/uploads/artists"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@router.get("/artists", tags=["artists"])
def list_artists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artists = (
        db.query(TrackArtist.artist_name)
        .filter(TrackArtist.artist_name.isnot(None))
        .group_by(TrackArtist.artist_name)
        .order_by(func.lower(TrackArtist.artist_name))
        .all()
    )

    return [artist[0] for artist in artists if artist[0]]


def build_mobile_artist_track_response(track: Track, db: Session) -> TrackResponse:
    album_key = normalize_album_name(track.album)
    artist_key = normalize_artist_name(track.artist)

    album_artwork = (
        db.query(AlbumArtwork)
        .filter(AlbumArtwork.album_key == album_key)
        .first()
    )
    artist_artwork = (
        db.query(ArtistArtwork)
        .filter(ArtistArtwork.artist_key == artist_key)
        .first()
    )

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
        duration_seconds=track.duration_seconds,
    )


@router.get("/mobile/artists", tags=["mobile"])
def list_mobile_artists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artist_rows = (
        db.query(
            TrackArtist.artist_name.label("artist_name"),
            func.count(func.distinct(TrackArtist.track_id)).label("track_count"),
        )
        .filter(TrackArtist.artist_name.isnot(None))
        .group_by(TrackArtist.artist_name)
        .order_by(func.lower(TrackArtist.artist_name))
        .all()
    )

    artist_keys = [normalize_artist_name(row.artist_name) for row in artist_rows if row.artist_name]
    artwork_rows = (
        db.query(ArtistArtwork)
        .filter(ArtistArtwork.artist_key.in_(artist_keys))
        .all()
        if artist_keys
        else []
    )
    artwork_by_key = {artwork.artist_key: artwork.artwork_path for artwork in artwork_rows}

    album_count_rows = (
        db.query(
            TrackArtist.artist_name.label("artist_name"),
            func.count(func.distinct(Track.album)).label("album_count"),
        )
        .join(Track, Track.id == TrackArtist.track_id)
        .filter(TrackArtist.artist_name.isnot(None))
        .filter(Track.album.isnot(None))
        .group_by(TrackArtist.artist_name)
        .all()
    )
    album_count_by_artist = {
        row.artist_name: row.album_count for row in album_count_rows if row.artist_name
    }

    return [
        {
            "name": row.artist_name,
            "artist": row.artist_name,
            "artist_name": row.artist_name,
            "trackCount": row.track_count,
            "track_count": row.track_count,
            "albumCount": album_count_by_artist.get(row.artist_name, 0),
            "album_count": album_count_by_artist.get(row.artist_name, 0),
            "artwork_path": artwork_by_key.get(normalize_artist_name(row.artist_name)),
            "artist_artwork_path": artwork_by_key.get(normalize_artist_name(row.artist_name)),
        }
        for row in artist_rows
        if row.artist_name
    ]


# New endpoint: /mobile/artists/section-index
@router.get("/mobile/artists/section-index", tags=["mobile"])
def get_mobile_artist_section_index(
    section: str = Query(..., pattern="^(\\$#|[A-Za-z])$"),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized_section = section.casefold()
    normalized_search = search.strip().casefold() if search else None

    query = (
        db.query(TrackArtist.artist_name.label("artist_name"))
        .filter(TrackArtist.artist_name.isnot(None))
        .group_by(TrackArtist.artist_name)
    )

    if normalized_search:
        query = query.filter(func.lower(TrackArtist.artist_name).contains(normalized_search))

    artists = [
        row.artist_name
        for row in query.order_by(func.lower(TrackArtist.artist_name)).all()
        if row.artist_name
    ]

    target_index = None
    target_artist = None

    for index, artist_name in enumerate(artists):
        first_character = artist_name.strip()[:1].casefold()

        if normalized_section == "$#":
            
            if not first_character.isalpha():
                target_index = index
                target_artist = artist_name
                break
        elif first_character == normalized_section:
            target_index = index
            target_artist = artist_name
            break

    return {
        "section": section.upper() if normalized_section != "$#" else "$#",
        "index": target_index,
        "artist_name": target_artist,
        "total": len(artists),
        "found": target_index is not None,
    }


@router.get("/mobile/artists/{artist_name:path}/tracks", response_model=list[TrackResponse], tags=["mobile"])
def get_mobile_artist_tracks(
    artist_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tracks = (
        db.query(Track)
        .join(TrackArtist, TrackArtist.track_id == Track.id)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(func.lower(TrackArtist.artist_name) == artist_name.casefold())
        .order_by(Track.album.asc(), Track.title.asc())
        .all()
    )

    return [build_mobile_artist_track_response(track, db) for track in tracks]


@router.get("/artists/artwork", tags=["artists"])
def get_all_artist_artwork(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artwork_rows = db.query(ArtistArtwork).all()

    return {
        "artwork": {
            artwork.artist_key: artwork.artwork_path
            for artwork in artwork_rows
            if artwork.artwork_path
        }
    }


@router.get("/artists/{artist_name:path}/tracks", response_model=list[TrackResponse], tags=["artists"])
def get_artist_tracks(
    artist_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_mobile_artist_tracks(
        artist_name=artist_name,
        db=db,
        current_user=current_user,
    )


@router.get("/artists/{artist_name:path}/artwork", tags=["artists"])
def get_artist_artwork(
    artist_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.post("/artists/{artist_name:path}/artwork", tags=["artists"])
def upload_artist_artwork(
    artist_name: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    artist_key = normalize_artist_name(artist_name)

    if not artist_key:
        raise HTTPException(status_code=400, detail="Invalid artist name")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    os.makedirs(ARTIST_ARTWORK_DIR, exist_ok=True)

    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        extension = ".jpg"

    filename = f"{uuid4().hex}{extension}"
    file_path = os.path.join(ARTIST_ARTWORK_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    artwork_path = f"/uploads/artists/{filename}"

    artwork = (
        db.query(ArtistArtwork)
        .filter(ArtistArtwork.artist_key == artist_key)
        .first()
    )

    if artwork:
        if artwork.artwork_path:
            old_filename = os.path.basename(artwork.artwork_path)
            old_file_path = os.path.join(ARTIST_ARTWORK_DIR, old_filename)

            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except OSError:
                    pass

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