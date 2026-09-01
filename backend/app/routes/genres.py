from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.track import Track
from app.models.track_genre import TrackGenre
from app.models.listening_event import ListeningEvent
from app.models.user import User
from app.services.track_responses import get_artwork_maps, normalize_album_key
from app.utils.artist_normalization import normalize_artist_name

router = APIRouter()


@router.get("/genres", tags=["genres"])
def list_genres(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    genres = (
        db.query(TrackGenre.genre)
        .distinct()
        .order_by(func.lower(TrackGenre.genre))
        .all()
    )

    return [g[0] for g in genres if g[0]]


@router.get("/genres/{genre_name}/tracks", tags=["genres"])
def list_genre_tracks(
    genre_name: str,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    play_counts = (
        db.query(
            ListeningEvent.track_id.label("track_id"),
            func.count(ListeningEvent.id).label("play_count"),
        )
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
        )
        .group_by(ListeningEvent.track_id)
        .subquery()
    )

    base_query = (
        db.query(
            Track,
            func.coalesce(play_counts.c.play_count, 0).label("play_count"),
        )
        .join(TrackGenre, TrackGenre.track_id == Track.id)
        .outerjoin(play_counts, play_counts.c.track_id == Track.id)
        .filter(func.lower(TrackGenre.genre) == func.lower(genre_name))
    )

    total = base_query.count()

    rows = (
        base_query
        .order_by(
            func.coalesce(play_counts.c.play_count, 0).desc(),
            func.lower(Track.title),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    # These used to read attributes the Track model does not have, so genre
    # lists always shipped null artwork. Two batched lookups fix that.
    album_map, artist_map = get_artwork_maps(db, [track for track, _count in rows])

    items = []

    for track, play_count in rows:
        album_artwork_path = album_map.get(normalize_album_key(track.album))

        items.append({
            "id": track.id,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "genre": track.genre,
            "genres": [genre_name],
            "file_path": track.file_path,
            "artwork_path": album_artwork_path,
            "album_artwork_path": album_artwork_path,
            "artist_artwork_path": artist_map.get(normalize_artist_name(track.artist)),
            "play_count": int(play_count or 0),
        })

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }