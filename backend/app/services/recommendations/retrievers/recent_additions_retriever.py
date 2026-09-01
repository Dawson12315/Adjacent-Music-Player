"""Recently added tracks that fit the profile.

Only used for the home "For You" feed. Without it, freshly imported music can
never surface — nothing links it to listening history yet, and the other
channels need history or curated context. Weighted low in ranking: this is an
exploration nudge, not a firehose of new files.
"""

from sqlalchemy.orm import Session, selectinload

from app.models.track import Track
from app.services.recommendations.genre_utils import get_track_families
from app.services.recommendations.types import RetrievedCandidate

RECENT_WINDOW = 400


def retrieve_recent_addition_candidates(
    db: Session,
    playlist_track_ids: list[int],
    playlist_profile: dict,
    limit: int = 60,
):
    candidates: dict[int, RetrievedCandidate] = {}

    family_counts = playlist_profile.get("family_counts", {})
    if not family_counts:
        return candidates

    excluded_ids = set(playlist_track_ids)

    recent_tracks = (
        db.query(Track)
        .options(selectinload(Track.track_genres))
        .order_by(Track.id.desc())
        .limit(RECENT_WINDOW)
        .all()
    )

    scored: list[tuple[float, int]] = []

    for recency_rank, track in enumerate(recent_tracks):
        if track.id in excluded_ids:
            continue

        shared = [
            family
            for family in get_track_families(track)
            if family in family_counts
        ]
        if not shared:
            continue

        recency = 1.0 - (recency_rank / RECENT_WINDOW)
        score = recency * (1.0 + 0.25 * (len(shared) - 1))
        scored.append((score, track.id))

    scored.sort(reverse=True)

    for score, track_id in scored[:limit]:
        candidate = candidates.setdefault(
            track_id,
            RetrievedCandidate(track_id=track_id),
        )
        candidate.add_score("recent", float(score))

    return candidates
