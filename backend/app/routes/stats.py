from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.track import Track
from app.models.listening_event import ListeningEvent
from app.models.track_genre import TrackGenre
from app.models.track_user_stats import TrackUserStats
from app.models.user import User
from app.models.album_artwork import AlbumArtwork
from app.routes.artists import artist_artwork_by_key
from app.routes.tracks import build_track_response as build_artwork_track_response
from app.schemas.track import TrackResponse, TrackWithStatsResponse
from app.services.timezones import (
    local_day_of,
    local_hour_of,
    normalize_zone_name,
    today_in,
    utc_start_of_day,
    zone_for,
)
from app.services.track_responses import (
    album_artwork_keys,
    build_track_payloads,
    build_track_responses,
)
from app.utils.artist_normalization import normalize_artist_name
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


def stats_zone(current_user: User, tz: str | None):
    """The zone this account's days and hours are counted in.

    `tz` is the client's hint — its device zone — and only stands in where
    the account has not chosen one in Settings. A name that is not a zone
    is refused rather than silently falling back to the server's.
    """
    override = None
    if tz:
        override = normalize_zone_name(tz)
        if override is None:
            raise HTTPException(status_code=422, detail=f"Unknown time zone: {tz}")
    return zone_for(getattr(current_user, "timezone", None), override)


def play_started_stamps(db: Session, user_id: int, since=None) -> list:
    """The timestamps of this account's play starts, oldest first."""
    query = db.query(ListeningEvent.created_at).filter(
        ListeningEvent.user_id == user_id,
        ListeningEvent.event_type == "play_started",
    )
    if since is not None:
        query = query.filter(ListeningEvent.created_at >= since)
    return [row.created_at for row in query.order_by(ListeningEvent.created_at.asc()).all() if row.created_at]


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
    return build_track_responses(db, tracks)


@router.get("/stats/most-liked", response_model=list[TrackResponse], tags=["stats"])
def most_liked_tracks(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tracks = get_most_liked_tracks(db, current_user.id, limit=limit)
    return build_track_responses(db, tracks)


@router.get("/stats/recently-played", tags=["stats"])
def recently_played_tracks(
    limit: int = Query(20, ge=1, le=500),
    fields: str | None = Query(None, pattern="^(list|full)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    tracks = get_recently_played_tracks(db, current_user.id, limit=limit)
    return build_track_payloads(db, tracks, fields)


def get_top_genres(db: Session, user_id: int, limit: int) -> list[dict]:
    rows = (
        db.query(
            TrackGenre.genre.label("name"),
            func.count(ListeningEvent.id).label("play_count"),
        )
        .join(Track, Track.id == TrackGenre.track_id)
        .join(ListeningEvent, ListeningEvent.track_id == Track.id)
        .filter(
            ListeningEvent.user_id == user_id,
            ListeningEvent.event_type == "play_started",
        )
        .group_by(TrackGenre.genre)
        .order_by(func.count(ListeningEvent.id).desc())
        .limit(limit)
        .all()
    )
    return [{"name": row.name, "play_count": row.play_count} for row in rows]


@router.get("/stats/top-genres", tags=["stats"])
def top_genres(
    limit: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The genres played most, and nothing else.

    The Genres page used to ask the overview for these, which builds four
    ranked track lists it then threw away.
    """
    return get_top_genres(db, current_user.id, limit)


@router.get("/stats/most-skipped", response_model=list[TrackResponse], tags=["stats"])
def get_most_skipped_tracks(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = get_most_skipped_tracks_for_user(db, current_user.id, limit=limit)

    # Batched like the other lists; a name-only helper here was a NameError
    # the moment a library had a skip to report.
    return build_track_responses(db, rows)


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
    tz: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    zone = stats_zone(current_user, tz)
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
    # they are counted in the listener's own zone — see services/timezones.
    active_days = sorted(
        {local_day_of(stamp, zone) for stamp in play_started_stamps(db, current_user.id)}
    )

    today = today_in(zone)
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
    tz: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # The listener's days, matching the summary's streaks.
    zone = stats_zone(current_user, tz)
    end_day = today_in(zone)
    start_day = end_day - timedelta(days=days - 1)

    plays_by_day: dict[str, int] = {}
    for stamp in play_started_stamps(db, current_user.id, since=utc_start_of_day(start_day, zone)):
        key = local_day_of(stamp, zone).isoformat()
        plays_by_day[key] = plays_by_day.get(key, 0) + 1

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

    # With a picture where the server has one, so a row can open the artist
    # page without the header flashing.
    keys = [normalize_artist_name(row.name) for row in artist_rows]
    artwork = artist_artwork_by_key(db, [key for key in keys if key])

    return [
        {
            "name": row.name,
            "play_count": row.play_count,
            "artwork_path": artwork.get(key) if key else None,
        }
        for row, key in zip(artist_rows, keys)
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

    wanted = {
        key
        for row in album_rows
        for key in album_artwork_keys(row.name, row.artist)
    }
    album_art = (
        {
            art.album_key: art.artwork_path
            for art in db.query(AlbumArtwork.album_key, AlbumArtwork.artwork_path)
            .filter(AlbumArtwork.album_key.in_(list(wanted)))
            .all()
            if art.artwork_path
        }
        if wanted
        else {}
    )

    def artwork_for(row):
        for key in album_artwork_keys(row.name, row.artist):
            if album_art.get(key):
                return album_art[key]
        return None

    return [
        {
            "name": row.name,
            "artist": row.artist,
            "play_count": row.play_count,
            "artwork_path": artwork_for(row),
        }
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
    tz: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # The listener's hours — "when you listen" in UTC put evening plays at 3 AM.
    zone = stats_zone(current_user, tz)
    plays_by_hour_value: dict[int, int] = {}
    for stamp in play_started_stamps(db, current_user.id):
        hour = local_hour_of(stamp, zone)
        plays_by_hour_value[hour] = plays_by_hour_value.get(hour, 0) + 1

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

    top_genres = get_top_genres(db, current_user.id, limit)

    # Batched, with artwork: the thin builder never set artwork paths, so the
    # Recently Played page fell back to generated tiles for anything outside
    # the first library page.
    return {
        "top_played": build_track_responses(db, top_played),
        "most_liked": build_track_responses(db, most_liked),
        "most_skipped": build_track_responses(db, most_skipped),
        "recently_played": build_track_responses(db, recently_played),
        "top_genres": top_genres,
    }
