from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.db import get_db

from app.models.track import Track
from app.models.track_user_stats import TrackUserStats

from app.schemas.track import TrackResponse
from app.services.stats_service import (
    get_most_liked_tracks,
    get_recently_played_tracks,
    get_top_played_tracks,
)
from app.services.recommendations.utils import build_track_response

router = APIRouter()


@router.get("/stats/top-played", response_model=list[TrackResponse], tags=["stats"])
def top_played_tracks(limit: int = 20, db: Session = Depends(get_db)):
    tracks = get_top_played_tracks(db, limit=limit)
    return [build_track_response(track) for track in tracks]


@router.get("/stats/most-liked", response_model=list[TrackResponse], tags=["stats"])
def most_liked_tracks(limit: int = 20, db: Session = Depends(get_db)):
    tracks = get_most_liked_tracks(db, limit=limit)
    return [build_track_response(track) for track in tracks]


@router.get("/stats/recently-played", response_model=list[TrackResponse], tags=["stats"])
def recently_played_tracks(limit: int = 20, db: Session = Depends(get_db)):
    tracks = get_recently_played_tracks(db, limit=limit)
    return [build_track_response(track) for track in tracks]


@router.get("/stats/most-skipped", response_model=list[TrackResponse], tags=["stats"])
def get_most_skipped_tracks(
    limit: int = 10,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Track)
        .join(TrackUserStats, TrackUserStats.track_id == Track.id)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(TrackUserStats.skip_count > 0)
        .order_by(
            TrackUserStats.skip_count.desc(),
            TrackUserStats.updated_at.desc(),
        )
        .limit(limit)
        .all()
    )

    return [build_track_response(track) for track in rows]

@router.get("/stats/overview", tags=["stats"])
def stats_overview(limit: int = 10, db: Session = Depends(get_db)):
    top_played = get_top_played_tracks(db, limit=limit)
    most_liked = get_most_liked_tracks(db, limit=limit)
    recently_played = get_recently_played_tracks(db, limit=limit)

    most_skipped = (
        db.query(Track)
        .join(TrackUserStats, TrackUserStats.track_id == Track.id)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(TrackUserStats.skip_count > 0)
        .order_by(
            TrackUserStats.skip_count.desc(),
            TrackUserStats.updated_at.desc(),
        )
        .limit(limit)
        .all()
    )

    return {
        "top_played": [build_track_response(track) for track in top_played],
        "most_liked": [build_track_response(track) for track in most_liked],
        "most_skipped": [build_track_response(track) for track in most_skipped],
        "recently_played": [build_track_response(track) for track in recently_played],
    }