import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, literal
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.utils.images import read_validated_image
from app.services.stream_cache_maintenance import has_room_for_upload
from app.dependencies.auth import get_current_user, require_admin
from app.models.album_artwork import AlbumArtwork
from app.models.track import Track
from app.models.user import User
from app.services.track_responses import build_track_responses

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

def paginate_flat(items: list, limit: int | None, offset: int):
    """Additive pagination — omitting `limit` keeps the historical flat list
    the deployed mobile app expects."""
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


@router.get("/mobile/albums", tags=["mobile"])
def list_mobile_albums(
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Grouped by album *and* artist: every library has several "Greatest
    # Hits", and grouping by title alone collapsed them into one tile with
    # whichever artist sorted first and every record's tracks interleaved.
    # One expression object for select, group and order: Postgres binds each
    # `coalesce(artist, '')` literal separately and then cannot see that the
    # grouped one is the selected one.
    artist_expr = func.coalesce(Track.artist, literal(""))
    album_rows = (
        db.query(
            Track.album.label("album"),
            artist_expr.label("artist"),
            func.count(Track.id).label("track_count"),
        )
        .filter(Track.album.isnot(None))
        .group_by(Track.album, artist_expr)
        .order_by(func.lower(Track.album), func.lower(artist_expr))
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

    items = [
        {
            # A stable identity a list can key on; `name` stays the title.
            "id": f"{row.album}\u001f{row.artist or ''}",
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

    return paginate_flat(items, limit, offset)


@router.get("/mobile/albums/{album_name:path}/tracks", tags=["mobile"])
def get_mobile_album_tracks(
    album_name: str,
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    # A plain default: another route calls this function directly, and a
    # Query() default would arrive as the marker object there.
    artist: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        # Same lowering function on both sides — see get_mobile_artist_tracks.
        .filter(func.lower(Track.album) == func.lower(album_name))
    )

    # Narrowed to one artist's record when the client names it; without it
    # every record of that title, as before.
    if isinstance(artist, str) and artist.strip():
        query = query.filter(func.lower(func.coalesce(Track.artist, "")) == artist.strip().lower()[:300])

    tracks = query.order_by(Track.title.asc()).all()

    return paginate_flat(build_track_responses(db, tracks), limit, offset)


@router.get("/albums/artwork", tags=["albums"])
def get_all_album_artwork(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artwork_rows = db.query(AlbumArtwork).all()

    return {
        "artwork": {
            artwork.album_key: artwork.artwork_path
            for artwork in artwork_rows
            if artwork.artwork_path
        }
    }


@router.get("/albums/{album_name:path}/tracks", tags=["albums"])
def get_album_tracks(
    album_name: str,
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_mobile_album_tracks(
        album_name=album_name,
        limit=limit,
        offset=offset,
        db=db,
        current_user=current_user,
    )


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

    # The bytes decide, not the declared type or the filename.
    image_bytes, extension = read_validated_image(file)

    if not has_room_for_upload(len(image_bytes)):
        raise HTTPException(status_code=507, detail="The server is out of disk space.")

    os.makedirs(ALBUM_ARTWORK_DIR, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    file_path = os.path.join(ALBUM_ARTWORK_DIR, filename)

    with open(file_path, "wb") as buffer:
        buffer.write(image_bytes)

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