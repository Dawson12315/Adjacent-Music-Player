import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.utils.images import read_validated_image
from app.services.stream_cache_maintenance import has_room_for_upload
from app.dependencies.auth import get_current_user, require_admin
from app.models.artist_artwork import ArtistArtwork
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.user import User
from app.services.track_responses import build_track_payloads, track_load_options
from app.utils.artist_normalization import normalize_artist_name

router = APIRouter()

# Stays under SQLite's bound-parameter ceiling.
_IN_CHUNK_SIZE = 500


def page_envelope(items: list, total: int, limit: int, offset: int) -> dict:
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


def artist_artwork_by_key(db: Session, keys: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for start in range(0, len(keys), _IN_CHUNK_SIZE):
        chunk = keys[start : start + _IN_CHUNK_SIZE]
        for row in (
            db.query(ArtistArtwork.artist_key, ArtistArtwork.artwork_path)
            .filter(ArtistArtwork.artist_key.in_(chunk))
            .all()
        ):
            out[row.artist_key] = row.artwork_path
    return out


def paginate_flat(items: list, limit: int | None, offset: int):
    """Additive pagination: no `limit` keeps the historical flat-list shape
    (the deployed mobile app depends on it); passing one returns the same
    envelope the web track list uses."""
    if limit is None:
        return items

    page = items[offset : offset + limit]

    return {
        "items": page,
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(page) < len(items),
    }

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


@router.get("/mobile/artists", tags=["mobile"])
def list_mobile_artists(
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # The page is cut in SQL. This used to aggregate every artist for every
    # page and slice the list in Python, so a 1,000-artist library paid for
    # the whole index twice per sign-in; the artwork and album-count lookups
    # now cover only the page, in chunks that fit SQLite's parameter limit.
    grouped = (
        db.query(
            TrackArtist.artist_name.label("artist_name"),
            func.count(func.distinct(TrackArtist.track_id)).label("track_count"),
        )
        .filter(TrackArtist.artist_name.isnot(None))
        .group_by(TrackArtist.artist_name)
        .order_by(func.lower(TrackArtist.artist_name))
    )

    if limit is None:
        artist_rows = grouped.all()
        total = len(artist_rows)
    else:
        total = (
            db.query(func.count(func.distinct(TrackArtist.artist_name)))
            .filter(TrackArtist.artist_name.isnot(None))
            .scalar()
            or 0
        )
        artist_rows = grouped.offset(offset).limit(limit).all()

    page_names = [row.artist_name for row in artist_rows if row.artist_name]
    artwork_by_key = artist_artwork_by_key(
        db, [normalize_artist_name(name) for name in page_names]
    )

    album_count_by_artist: dict[str, int] = {}
    for start in range(0, len(page_names), _IN_CHUNK_SIZE):
        chunk = page_names[start : start + _IN_CHUNK_SIZE]
        for row in (
            db.query(
                TrackArtist.artist_name.label("artist_name"),
                func.count(func.distinct(Track.album)).label("album_count"),
            )
            .join(Track, Track.id == TrackArtist.track_id)
            .filter(TrackArtist.artist_name.in_(chunk))
            .filter(Track.album.isnot(None))
            .group_by(TrackArtist.artist_name)
            .all()
        ):
            album_count_by_artist[row.artist_name] = row.album_count

    items = [
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

    if limit is None:
        return items

    return page_envelope(items, total, limit, offset)


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


@router.get("/mobile/artists/{artist_name:path}/tracks", tags=["mobile"])
def get_mobile_artist_tracks(
    artist_name: str,
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    # A plain default: the web route calls this function directly.
    fields: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not isinstance(fields, str):
        fields = None

    tracks = (
        db.query(Track)
        .join(TrackArtist, TrackArtist.track_id == Track.id)
        .options(*track_load_options(fields))
        # Lower both sides with the SAME function (SQLite's). Mixing SQL
        # lower() with Python casefold() made names containing ß/İ-class
        # characters unmatchable.
        .filter(func.lower(TrackArtist.artist_name) == func.lower(artist_name))
        .order_by(Track.album.asc(), Track.title.asc())
        .all()
    )

    return paginate_flat(build_track_payloads(db, tracks, fields), limit, offset)


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


@router.get("/artists/{artist_name:path}/tracks", tags=["artists"])
def get_artist_tracks(
    artist_name: str,
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_mobile_artist_tracks(
        artist_name=artist_name,
        limit=limit,
        offset=offset,
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

    # The bytes decide, not the declared type or the filename.
    image_bytes, extension = read_validated_image(file)

    if not has_room_for_upload(len(image_bytes)):
        raise HTTPException(status_code=507, detail="The server is out of disk space.")

    os.makedirs(ARTIST_ARTWORK_DIR, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    file_path = os.path.join(ARTIST_ARTWORK_DIR, filename)

    with open(file_path, "wb") as buffer:
        buffer.write(image_bytes)

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