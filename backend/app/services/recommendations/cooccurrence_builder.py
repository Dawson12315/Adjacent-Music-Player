"""Builds the track co-occurrence table.

Two sources, combined:

- Listening sessions: tracks played near each other in the same session
  (`listening_events.session_id`), weighted by proximity. This is the richest
  personal signal a self-hosted server has — it is literally "what the user
  plays together" — and it accumulates on its own as the app is used.
- Playlist co-membership: tracks deliberately curated together. Weighted
  higher per pair than a single session adjacency, because curation is an
  explicit statement; sessions catch up through repetition.

The table is rebuilt from scratch — event counts are small (thousands) and a
full rebuild is O(events + playlist pairs), so incremental bookkeeping is not
worth its complexity. Playlist pairs are what make that go wrong: a liked-songs
list of two thousand tracks is two million pairs on its own, which took eight
gigabytes and held SQLite's write lock for most of a minute nightly and at
boot. Large playlists are sampled, and the rows go in with bulk inserts in
chunks, committing as they go.
"""

import logging
import random
from collections import Counter
from itertools import combinations

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.listening_event import ListeningEvent
from app.models.playlist_track import PlaylistTrack
from app.models.track_cooccurrence import TrackCooccurrence

# Above this many tracks a playlist is a library, not a curation: every track
# is paired with a sample of the others rather than with all of them.
PLAYLIST_FULL_PAIRS_UP_TO = 300
PLAYLIST_SAMPLE_PARTNERS = 40

# Rows per INSERT and per commit.
INSERT_CHUNK = 5000


logger = logging.getLogger(__name__)

# Pairs further apart than this in a session are not counted.
SESSION_PAIR_MAX_GAP = 10

# Guards the O(n · gap) pair expansion against pathological sessions.
SESSION_MAX_EVENTS = 500

PLAYLIST_PAIR_WEIGHT = 2.0


def _session_pair_weight(gap: int) -> float:
    if gap <= 2:
        return 1.0
    if gap <= 5:
        return 0.5
    return 0.25


def _collect_session_pairs(db: Session) -> Counter:
    rows = (
        db.query(
            ListeningEvent.session_id,
            ListeningEvent.track_id,
        )
        .filter(
            ListeningEvent.event_type == "play_started",
            ListeningEvent.session_id.isnot(None),
        )
        .order_by(ListeningEvent.session_id.asc(), ListeningEvent.created_at.asc())
        .all()
    )

    pair_weights: Counter = Counter()

    def flush(sequence: list[int]):
        # Collapse immediate repeats (loops of one track) so they do not pair
        # with themselves through the window.
        deduped: list[int] = []
        for track_id in sequence:
            if not deduped or deduped[-1] != track_id:
                deduped.append(track_id)

        deduped = deduped[:SESSION_MAX_EVENTS]

        for index, track_a in enumerate(deduped):
            for gap in range(1, SESSION_PAIR_MAX_GAP + 1):
                partner_index = index + gap
                if partner_index >= len(deduped):
                    break

                track_b = deduped[partner_index]
                if track_a == track_b:
                    continue

                pair = (track_a, track_b) if track_a < track_b else (track_b, track_a)
                pair_weights[pair] += _session_pair_weight(gap)

    current_session = None
    sequence: list[int] = []

    for session_id, track_id in rows:
        if session_id != current_session:
            if sequence:
                flush(sequence)
            current_session = session_id
            sequence = []

        sequence.append(track_id)

    if sequence:
        flush(sequence)

    return pair_weights


def _collect_playlist_pairs(db: Session) -> tuple[Counter, int]:
    playlist_rows = (
        db.query(PlaylistTrack)
        .order_by(PlaylistTrack.playlist_id.asc(), PlaylistTrack.position.asc())
        .all()
    )

    playlist_to_tracks: dict[int, list[int]] = {}
    for row in playlist_rows:
        playlist_to_tracks.setdefault(row.playlist_id, []).append(row.track_id)

    pair_weights: Counter = Counter()

    rng = random.Random(0)

    for track_ids in playlist_to_tracks.values():
        unique_track_ids = sorted(set(track_ids))

        if len(unique_track_ids) < 2:
            continue

        if len(unique_track_ids) <= PLAYLIST_FULL_PAIRS_UP_TO:
            for pair in combinations(unique_track_ids, 2):
                pair_weights[pair] += PLAYLIST_PAIR_WEIGHT
            continue

        # Sampled: each track keeps a bounded number of partners, so the pair
        # count grows with the playlist rather than with its square. Seeded,
        # so two rebuilds of the same data agree.
        for track_a in unique_track_ids:
            for track_b in rng.sample(unique_track_ids, PLAYLIST_SAMPLE_PARTNERS):
                if track_a == track_b:
                    continue
                pair = (track_a, track_b) if track_a < track_b else (track_b, track_a)
                pair_weights[pair] += PLAYLIST_PAIR_WEIGHT

    return pair_weights, len(playlist_to_tracks)


def rebuild_track_cooccurrence(db: Session) -> dict:
    session_pairs = _collect_session_pairs(db)
    playlist_pairs, playlists_scanned = _collect_playlist_pairs(db)

    combined: Counter = Counter()
    combined.update(session_pairs)
    combined.update(playlist_pairs)

    db.query(TrackCooccurrence).delete()
    db.commit()

    # Core inserts in chunks, each its own transaction: no ORM object per
    # pair, and the write lock is released between chunks so a like or a
    # play recorded during the rebuild is not made to wait a minute.
    table = TrackCooccurrence.__table__
    rows = []
    pairs_written = 0

    for (track_a_id, track_b_id), weight in combined.items():
        rows.append(
            {
                "track_a_id": track_a_id,
                "track_b_id": track_b_id,
                "cooccurrence_count": int(round(weight)),
            }
        )

        if len(rows) >= INSERT_CHUNK:
            db.execute(insert(table), rows)
            db.commit()
            pairs_written += len(rows)
            rows = []

    if rows:
        db.execute(insert(table), rows)
        db.commit()
        pairs_written += len(rows)

    result = {
        "playlists_scanned": playlists_scanned,
        "session_pairs": len(session_pairs),
        "playlist_pairs": len(playlist_pairs),
        "pairs_written": pairs_written,
    }
    logger.info("Rebuilt track co-occurrence: %s", result)
    return result


COOCCURRENCE_JOB_NAME = "cooccurrence_rebuild"


def rebuild_track_cooccurrence_standalone() -> dict:
    """For the scheduler and background hooks — owns its session.

    Holds a job lock for the duration so the Postgres migration refuses to
    start over it (the rebuild rewrites a whole table; half of it landing
    after the snapshot would be silently lost), and skips itself when a
    migration is already pausing writes.
    """
    from app.services import maintenance_mode
    from app.services.job_locking import release_job_lock, try_acquire_job_lock

    if maintenance_mode.writes_paused():
        logger.info("Co-occurrence rebuild skipped: database migration in progress")
        return {"skipped": "migration_in_progress"}

    db = SessionLocal()
    try:
        if not try_acquire_job_lock(db, COOCCURRENCE_JOB_NAME):
            logger.info("Co-occurrence rebuild skipped: already running")
            return {"skipped": "already_running"}

        try:
            return rebuild_track_cooccurrence(db)
        finally:
            try:
                release_job_lock(db, COOCCURRENCE_JOB_NAME)
            except Exception:  # noqa: BLE001
                logger.warning("Could not release the co-occurrence job lock", exc_info=True)
    finally:
        db.close()


def main() -> None:
    logger.info(rebuild_track_cooccurrence_standalone())


if __name__ == "__main__":
    main()
