from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.listening_event import ListeningEvent
from app.models.track import Track
from app.models.track_user_stats import TrackUserStats
from app.schemas.listening import ListeningEventCreate


def _get_or_create_track_stats(db: Session, user_id: int, track_id: int) -> TrackUserStats:
    stats = (
        db.query(TrackUserStats)
        .filter(
            TrackUserStats.user_id == user_id,
            TrackUserStats.track_id == track_id,
        )
        .first()
    )

    if stats:
        return stats

    stats = TrackUserStats(
        user_id=user_id,
        track_id=track_id,
    )

    db.add(stats)

    try:
        db.flush()
        return stats
    except IntegrityError:
        db.rollback()

        stats = (
            db.query(TrackUserStats)
            .filter(
                TrackUserStats.user_id == user_id,
                TrackUserStats.track_id == track_id,
            )
            .first()
        )

        if not stats:
            raise

        return stats


def _calculate_completion_ratio(
    position_seconds: float | None,
    duration_seconds: float | None,
    event_type: str,
) -> float | None:
    if event_type == "play_completed":
        return 1.0

    if event_type != "skipped":
        return None

    if position_seconds is None or duration_seconds is None or duration_seconds <= 0:
        return None

    ratio = position_seconds / duration_seconds
    return max(0.0, min(ratio, 1.0))


def _later(current, candidate):
    """Never move last-played backwards when an older event is replayed."""
    if current is None:
        return candidate
    try:
        return max(current, candidate)
    except TypeError:
        return candidate


def record_listening_event(
    db: Session,
    payload: ListeningEventCreate,
    user_id: int,
) -> ListeningEvent:
    track = db.query(Track).filter(Track.id == payload.track_id).first()
    if not track:
        raise ValueError("Track not found")

    now = datetime.now(UTC)
    # The client's clock when it says so, bounded to the recent past: a play
    # replayed from an outbox after a flight lands in the hour it happened.
    # A time in the future, or older than the outbox keeps, is a bad clock.
    occurred_at = getattr(payload, "occurred_at", None)
    if occurred_at is not None:
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        if occurred_at > now or now - occurred_at > timedelta(days=7):
            occurred_at = None
    happened_at = (occurred_at or now).replace(tzinfo=None)

    event = ListeningEvent(
        user_id=user_id,
        track_id=payload.track_id,
        event_type=payload.event_type,
        source_type=payload.source_type,
        source_id=payload.source_id,
        position_seconds=payload.position_seconds,
        duration_seconds=payload.duration_seconds,
        session_id=payload.session_id,
        created_at=happened_at,
    )

    db.add(event)

    stats = _get_or_create_track_stats(db, user_id, payload.track_id)

    ratio_event_count_before = stats.completion_count + stats.skip_count

    if payload.event_type == "play_started":
        stats.play_count += 1
        stats.last_played_at = _later(stats.last_played_at, happened_at)

    elif payload.event_type == "skipped":
        stats.skip_count += 1
        stats.last_played_at = _later(stats.last_played_at, happened_at)

    elif payload.event_type == "play_completed":
        stats.completion_count += 1
        stats.last_played_at = _later(stats.last_played_at, happened_at)

    elif payload.event_type == "liked":
        stats.like_count += 1

    elif payload.event_type == "unliked":
        stats.like_count = max(0, stats.like_count - 1)

    elif payload.event_type == "playlist_added":
        stats.playlist_add_count += 1

    elif payload.event_type == "playlist_removed":
        stats.playlist_add_count = max(0, stats.playlist_add_count - 1)

    completion_ratio = _calculate_completion_ratio(
        payload.position_seconds,
        payload.duration_seconds,
        payload.event_type,
    )

    if completion_ratio is not None:
        ratio_event_count_after = ratio_event_count_before + 1
        stats.avg_completion_ratio = (
            (stats.avg_completion_ratio * ratio_event_count_before) + completion_ratio
        ) / ratio_event_count_after

    stats.replay_score = max(0.0, stats.play_count - (stats.skip_count * 0.5))
    stats.updated_at = now

    db.commit()
    db.refresh(event)

    return event