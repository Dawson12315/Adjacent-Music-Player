from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.track import Track
from app.models.track_genre import TrackGenre
from app.models.listening_event import ListeningEvent
from app.models.user import User

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
        .filter(func.lower(TrackGenre.genre) == genre_name.lower())
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

    items = []

    for track, play_count in rows:
        items.append({
            "id": track.id,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "genre": track.genre,
            "genres": [genre_name],
            "file_path": track.file_path,
            "artwork_path": getattr(track, "artwork_path", None),
            "album_artwork_path": getattr(track, "album_artwork_path", None),
            "artist_artwork_path": getattr(track, "artist_artwork_path", None),
            "play_count": int(play_count or 0),
        })

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }