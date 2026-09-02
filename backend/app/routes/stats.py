from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.track import Track
from app.models.listening_event import ListeningEvent
from app.models.track_genre import TrackGenre
from app.models.track_user_stats import TrackUserStats
from app.models.user import User
from app.routes.tracks import build_track_response as build_artwork_track_response
from app.utils.db_compat import hour_of_day
from app.schemas.track import TrackResponse, TrackWithStatsResponse
from app.services.recommendations.utils import build_track_response
from app.services.stats_service import (
    get_most_liked_tracks,
    get_most_liked_tracks_with_stats,
    get_most_skipped_tracks as get_most_skipped_tracks_for_user,
    get_most_skipped_tracks_with_stats,
    get_recently_played_tracks,
    get_recently_played_tracks_with_stats,
    get_top_played_tracks,
    get_top_played_tracks_with_stats,
)

router = APIRouter()


def build_track_with_stats_response(
    track: Track,
    stats: TrackUserStats | None,
    db: Session,
) -> TrackWithStatsResponse:
    return TrackWithStatsResponse(
        **build_artwork_track_response(track, db).model_dump(),
        play_count=stats.play_count if stats else 0,
        skip_count=stats.skip_count if stats else 0,
        completion_count=stats.completion_count if stats else 0,
        like_count=stats.like_count if stats else 0,
        last_played_at=stats.last_played_at if stats else None,
    )


@router.get("/stats/top-played", response_model=list[TrackResponse], tags=["stats"])
def top_played_tracks(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tracks = get_top_played_tracks(db, current_user.id, limit=limit)
    return [build_track_response(track) for track in tracks]


@router.get("/stats/most-liked", response_model=list[TrackResponse], tags=["stats"])
def most_liked_tracks(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tracks = get_most_liked_tracks(db, current_user.id, limit=limit)
    return [build_track_response(track) for track in tracks]


@router.get("/stats/recently-played", response_model=list[TrackResponse], tags=["stats"])
def recently_played_tracks(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tracks = get_recently_played_tracks(db, current_user.id, limit=limit)
    return [build_track_response(track) for track in tracks]


@router.get("/stats/most-skipped", response_model=list[TrackResponse], tags=["stats"])
def get_most_skipped_tracks(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = get_most_skipped_tracks_for_user(db, current_user.id, limit=limit)

    return [build_track_response(track) for track in rows]


@router.get(
    "/stats/top-played-detailed",
    response_model=list[TrackWithStatsResponse],
    tags=["stats"],
)
def top_played_tracks_detailed(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = get_top_played_tracks_with_stats(db, current_user.id, limit=limit)

    return [build_track_with_stats_response(track, stats, db) for track, stats in rows]


@router.get(
    "/stats/most-liked-detailed",
    response_model=list[TrackWithStatsResponse],
    tags=["stats"],
)
def most_liked_tracks_detailed(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = get_most_liked_tracks_with_stats(db, current_user.id, limit=limit)

    return [build_track_with_stats_response(track, stats, db) for track, stats in rows]


@router.get(
    "/stats/most-skipped-detailed",
    response_model=list[TrackWithStatsResponse],
    tags=["stats"],
)
def most_skipped_tracks_detailed(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = get_most_skipped_tracks_with_stats(db, current_user.id, limit=limit)

    return [build_track_with_stats_response(track, stats, db) for track, stats in rows]


@router.get(
    "/stats/recently-played-detailed",
    response_model=list[TrackWithStatsResponse],
    tags=["stats"],
)
def recently_played_tracks_detailed(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = get_recently_played_tracks_with_stats(db, current_user.id, limit=limit)

    return [build_track_with_stats_response(track, stats, db) for track, stats in rows]


@router.get("/stats/summary", tags=["stats"])
def stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event_count_rows = (
        db.query(
            ListeningEvent.event_type.label("event_type"),
            func.count(ListeningEvent.id).label("event_count"),
        )
        .filter(ListeningEvent.user_id == current_user.id)
        .group_by(ListeningEvent.event_type)
        .all()
    )
    counts_by_event_type = {row.event_type: row.event_count for row in event_count_rows}

    total_plays = counts_by_event_type.get("play_started", 0)
    total_skips = counts_by_event_type.get("skipped", 0)
    total_completions = counts_by_event_type.get("play_completed", 0)

    play_totals = (
        db.query(
            func.count(func.distinct(ListeningEvent.track_id)).label("distinct_tracks"),
            func.count(func.distinct(Track.artist)).label("distinct_artists"),
            func.min(ListeningEvent.created_at).label("first_played_at"),
            func.max(ListeningEvent.created_at).label("last_played_at"),
        )
        .join(Track, Track.id == ListeningEvent.track_id)
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
        )
        .one()
    )

    completed_seconds = (
        db.query(func.coalesce(func.sum(ListeningEvent.duration_seconds), 0.0))
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_completed",
        )
        .scalar()
    )

    skipped_seconds = (
        db.query(func.coalesce(func.sum(ListeningEvent.position_seconds), 0.0))
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "skipped",
        )
        .scalar()
    )

    # Timestamps are stored in UTC; days and streaks are a human concept, so
    # bucket them in the server's local timezone or evening listening bleeds
    # into the next day.
    active_day_rows = (
        db.query(func.date(ListeningEvent.created_at, "localtime").label("day"))
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
        )
        .group_by(func.date(ListeningEvent.created_at, "localtime"))
        .all()
    )

    active_days = sorted(
        date.fromisoformat(row.day) for row in active_day_rows if row.day
    )

    today = datetime.now().date()
    current_streak_days = 0

    if active_days and active_days[-1] in (today, today - timedelta(days=1)):
        current_streak_days = 1
        expected_day = active_days[-1] - timedelta(days=1)

        for active_day in reversed(active_days[:-1]):
            if active_day != expected_day:
                break

            current_streak_days += 1
            expected_day = active_day - timedelta(days=1)

    longest_streak_days = 0
    running_streak_days = 0
    previous_day = None

    for active_day in active_days:
        if previous_day is not None and active_day == previous_day + timedelta(days=1):
            running_streak_days += 1
        else:
            running_streak_days = 1

        longest_streak_days = max(longest_streak_days, running_streak_days)
        previous_day = active_day

    return {
        "total_plays": total_plays,
        "total_skips": total_skips,
        "total_completions": total_completions,
        "distinct_tracks_played": play_totals.distinct_tracks or 0,
        "distinct_artists_played": play_totals.distinct_artists or 0,
        "days_active": len(active_days),
        "first_played_at": play_totals.first_played_at,
        "last_played_at": play_totals.last_played_at,
        "completion_rate": (total_completions / total_plays) if total_plays else 0.0,
        # Skips are a subset of started plays (a skip always follows a
        # play_started), so the denominator is plays — adding skips to it
        # double-counted them and understated the rate.
        "skip_rate": min(total_skips / total_plays, 1.0) if total_plays else 0.0,
        "estimated_listening_seconds": float(completed_seconds or 0.0)
        + float(skipped_seconds or 0.0),
        "current_streak_days": current_streak_days,
        "longest_streak_days": longest_streak_days,
    }


@router.get("/stats/plays-over-time", tags=["stats"])
def plays_over_time(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Local days, matching the summary's streaks — see the note there.
    end_day = datetime.now().date()
    start_day = end_day - timedelta(days=days - 1)

    play_rows = (
        db.query(
            func.date(ListeningEvent.created_at, "localtime").label("day"),
            func.count(ListeningEvent.id).label("plays"),
        )
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
            func.date(ListeningEvent.created_at, "localtime") >= start_day.isoformat(),
        )
        .group_by(func.date(ListeningEvent.created_at, "localtime"))
        .all()
    )

    plays_by_day = {row.day: row.plays for row in play_rows if row.day}

    return [
        {
            "date": (start_day + timedelta(days=offset)).isoformat(),
            "plays": plays_by_day.get((start_day + timedelta(days=offset)).isoformat(), 0),
        }
        for offset in range(days)
    ]


@router.get("/stats/top-artists", tags=["stats"])
def top_artists(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artist_rows = (
        db.query(
            Track.artist.label("name"),
            func.count(ListeningEvent.id).label("play_count"),
        )
        .join(ListeningEvent, ListeningEvent.track_id == Track.id)
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
            Track.artist.isnot(None),
            Track.artist != "",
        )
        .group_by(Track.artist)
        .order_by(func.count(ListeningEvent.id).desc())
        .limit(limit)
        .all()
    )

    return [
        {"name": row.name, "play_count": row.play_count}
        for row in artist_rows
    ]


@router.get("/stats/top-albums", tags=["stats"])
def top_albums(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    album_rows = (
        db.query(
            Track.album.label("name"),
            func.min(Track.artist).label("artist"),
            func.count(ListeningEvent.id).label("play_count"),
        )
        .join(ListeningEvent, ListeningEvent.track_id == Track.id)
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
            Track.album.isnot(None),
            Track.album != "",
        )
        .group_by(Track.album)
        .order_by(func.count(ListeningEvent.id).desc())
        .limit(limit)
        .all()
    )

    return [
        {"name": row.name, "artist": row.artist, "play_count": row.play_count}
        for row in album_rows
    ]


@router.get("/stats/by-source", tags=["stats"])
def plays_by_source(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source_rows = (
        db.query(
            ListeningEvent.source_type.label("source"),
            func.count(ListeningEvent.id).label("plays"),
        )
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
        )
        .group_by(ListeningEvent.source_type)
        .all()
    )

    plays_by_source_name: dict[str, int] = {}

    for row in source_rows:
        source_name = row.source or "unknown"
        plays_by_source_name[source_name] = (
            plays_by_source_name.get(source_name, 0) + row.plays
        )

    return [
        {"source": source_name, "plays": plays}
        for source_name, plays in sorted(
            plays_by_source_name.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]


@router.get("/stats/by-hour", tags=["stats"])
def plays_by_hour(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Local hours — "when you listen" in UTC put evening plays at 3 AM.
    hour_expr = hour_of_day(ListeningEvent.created_at)
    hour_rows = (
        db.query(
            hour_expr.label("hour"),
            func.count(ListeningEvent.id).label("plays"),
        )
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
        )
        .group_by(hour_expr)
        .all()
    )

    plays_by_hour_value = {
        int(row.hour): row.plays for row in hour_rows if row.hour is not None
    }

    return [
        {"hour": hour, "plays": plays_by_hour_value.get(hour, 0)}
        for hour in range(24)
    ]


@router.get("/stats/overview", tags=["stats"])
def stats_overview(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    top_played = get_top_played_tracks(db, current_user.id, limit=limit)
    most_liked = get_most_liked_tracks(db, current_user.id, limit=limit)
    recently_played = get_recently_played_tracks(db, current_user.id, limit=limit)

    most_skipped = get_most_skipped_tracks_for_user(db, current_user.id, limit=limit)

    top_genres = (
        db.query(
            TrackGenre.genre.label("name"),
            func.count(ListeningEvent.id).label("play_count"),
        )
        .join(Track, Track.id == TrackGenre.track_id)
        .join(ListeningEvent, ListeningEvent.track_id == Track.id)
        .filter(
            ListeningEvent.user_id == current_user.id,
            ListeningEvent.event_type == "play_started",
        )
        .group_by(TrackGenre.genre)
        .order_by(func.count(ListeningEvent.id).desc())
        .limit(limit)
        .all()
    )

    return {
        "top_played": [build_track_response(track) for track in top_played],
        "most_liked": [build_track_response(track) for track in most_liked],
        "most_skipped": [build_track_response(track) for track in most_skipped],
        "recently_played": [build_track_response(track) for track in recently_played],
        "top_genres": [
            {"name": genre.name, "play_count": genre.play_count}
            for genre in top_genres
        ],
    }
