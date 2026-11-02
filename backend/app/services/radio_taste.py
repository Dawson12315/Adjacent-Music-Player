"""What the thumbs leave behind: a listener's standing corrections to the map.

A thumb on a station says two things. Right now, it says where this station
should lean: that is `station_query` (relevance feedback on the seeds'
position — toward thumbed-up tracks, away from thumbed-down tracks and
artists), applied to the next batch and gone with the station.

It also says something small and lasting about one listener's sense of one
artist. That is a correction: a bounded vector added to the artist's
position for this listener only, nudged a step toward the station's seeds
on "more" and away on "less", decaying over months, never large enough to
move an artist out of its own neighbourhood. Corrections live on the
account, survive the station, and have a visible reset.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from app.models.listener_artist_correction import ListenerArtistCorrection
from app.services.recommendations.rec_cache import get_or_build, invalidate
from app.services.recommendations.vector_map import VectorIndex

# One vote moves the artist this far along the line to (or from) the
# station's seeds, as a fraction of the way.
STEP = 0.15
# A correction never exceeds this length; artist positions are unit
# vectors, so it can lean an artist, not relocate it.
MAX_SHIFT = 0.35
# Half-life of a correction, in days: a thumb from last winter still
# counts, a little.
HALF_LIFE_DAYS = 180.0
# The station's own lean: how far the query moves toward what was thumbed
# up and away from what was thumbed down.
TOWARD = 0.5
AWAY = 0.5
CACHE_TTL_SECONDS = 180


def _decay(age_seconds: float) -> float:
    return 0.5 ** (max(0.0, age_seconds) / (HALF_LIFE_DAYS * 86400.0))


def station_query(index: VectorIndex, seed_ids, more_ids=(), less_ids=(), less_artist_keys=()) -> np.ndarray | None:
    """The station's position: the seeds, leaned by what the listener said."""
    query = index.query_from(seed_ids)
    if query is None:
        return None
    return index.steer(query, more_ids=more_ids, less_ids=less_ids, less_artist_keys=less_artist_keys, toward=TOWARD, away=AWAY)


def record_vote(db: Session, index: VectorIndex | None, user_id: int, artist_key: str, artist_name: str | None, context: np.ndarray | None, up: bool) -> None:
    """Nudge the listener's correction for this artist toward (`up`) or away
    from the station's position `context`. No map, no context, no artist on
    the map: nothing to record."""
    if index is None or context is None or not artist_key:
        return
    base = index.artist_vector(artist_key)
    if base is None:
        return
    direction = context.astype(np.float32) - base
    norm = float(np.linalg.norm(direction))
    if norm <= 1e-6:
        return
    direction /= norm
    now = datetime.utcnow()
    row = (
        db.query(ListenerArtistCorrection)
        .filter(ListenerArtistCorrection.user_id == user_id, ListenerArtistCorrection.artist_key == artist_key)
        .first()
    )
    if row is None or row.dim != index.dim:
        delta = np.zeros(index.dim, dtype=np.float32)
        if row is None:
            row = ListenerArtistCorrection(user_id=user_id, artist_key=artist_key, artist_name=artist_name, delta=delta.tobytes(), dim=index.dim)
            db.add(row)
    else:
        delta = np.frombuffer(row.delta, dtype=np.float32).copy() * _decay((now - row.updated_at).total_seconds())
    delta += (STEP if up else -STEP) * direction
    length = float(np.linalg.norm(delta))
    if length > MAX_SHIFT:
        delta *= MAX_SHIFT / length
    row.delta = delta.astype(np.float32).tobytes()
    row.dim = index.dim
    row.artist_name = artist_name or row.artist_name
    if up:
        row.votes_up = (row.votes_up or 0) + 1
    else:
        row.votes_down = (row.votes_down or 0) + 1
    row.updated_at = now
    db.commit()
    invalidate(_cache_key(user_id))


def _cache_key(user_id: int) -> str:
    return f"radio_taste:{user_id}"


def _load(db: Session, user_id: int, dim: int) -> dict[str, np.ndarray]:
    now = datetime.utcnow()
    out: dict[str, np.ndarray] = {}
    for row in db.query(ListenerArtistCorrection).filter(ListenerArtistCorrection.user_id == user_id):
        if row.dim != dim:
            continue
        delta = np.frombuffer(row.delta, dtype=np.float32) * _decay((now - row.updated_at).total_seconds())
        if float(np.linalg.norm(delta)) > 1e-4:
            out[row.artist_key] = delta.astype(np.float32)
    return out


def corrections_for(db: Session, user_id: int | None, index: VectorIndex | None) -> dict[str, np.ndarray]:
    """This listener's corrections, decayed to today, keyed by artist."""
    if user_id is None or index is None:
        return {}
    return get_or_build(_cache_key(user_id), lambda: _load(db, user_id, index.dim), ttl_seconds=CACHE_TTL_SECONDS)


def summary(db: Session, user_id: int) -> dict:
    rows = db.query(ListenerArtistCorrection).filter(ListenerArtistCorrection.user_id == user_id).all()
    return {
        "artists": len(rows),
        "votes_up": int(sum(row.votes_up or 0 for row in rows)),
        "votes_down": int(sum(row.votes_down or 0 for row in rows)),
    }


def reset(db: Session, user_id: int) -> int:
    count = db.query(ListenerArtistCorrection).filter(ListenerArtistCorrection.user_id == user_id).delete(synchronize_session=False)
    db.commit()
    invalidate(_cache_key(user_id))
    return int(count or 0)


def expected_shift(votes: int) -> float:
    """How far `votes` thumbs in one direction move an artist, for tests and
    the docs: STEP each, capped at MAX_SHIFT."""
    return min(MAX_SHIFT, STEP * votes) if votes > 0 else 0.0


__all__ = ["station_query", "record_vote", "corrections_for", "summary", "reset", "expected_shift", "STEP", "MAX_SHIFT", "HALF_LIFE_DAYS", "math"]
