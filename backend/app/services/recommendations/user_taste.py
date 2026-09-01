"""User taste profile derived from listening stats.

This is the "gets better with use" layer: the same per-track stats that feed
the insights page (plays, likes, completions, skips) are aggregated into
family- and artist-level affinities plus per-track skip aversions.

Personalization is deliberately bounded, twice over:

- Its weight ramps with *confidence* — how much history exists. A fresh
  account contributes nothing; the full effect needs ~CONFIDENCE_FULL_PLAYS
  plays. The system never guesses taste from three plays.
- Even at full confidence it is additive and capped (MAX_TASTE_BONUS /
  MAX_SKIP_PENALTY), sized to shift ties and near-ties, not to override the
  content channels — a strongly matching track always beats a merely
  familiar one.
"""

from collections import Counter

from sqlalchemy.orm import Session, selectinload

from app.models.track import Track
from app.models.track_user_stats import TrackUserStats
from app.services.recommendations.genre_utils import get_track_families

# Plays needed before personal taste reaches full strength.
CONFIDENCE_FULL_PLAYS = 500

# Ceilings on personalization inside the final score (content signals span
# roughly 0–10 after ranking; these can nudge, not dominate).
MAX_TASTE_BONUS = 1.5
MAX_SKIP_PENALTY = 1.5

# A track needs at least this many interactions before its skip ratio counts.
MIN_INTERACTIONS_FOR_SKIP_SIGNAL = 3


def _normalize_artist_key(value: str | None) -> str:
    return (value or "").strip().casefold()


def build_user_taste_profile(db: Session, user_id: int | None) -> dict | None:
    if user_id is None:
        return None

    rows = (
        db.query(Track, TrackUserStats)
        .join(TrackUserStats, TrackUserStats.track_id == Track.id)
        .options(selectinload(Track.track_genres))
        .filter(TrackUserStats.user_id == user_id)
        .all()
    )

    if not rows:
        return None

    family_weights: Counter = Counter()
    artist_weights: Counter = Counter()
    skip_ratio_by_track: dict[int, float] = {}
    total_plays = 0

    for track, stats in rows:
        plays = int(stats.play_count or 0)
        likes = int(stats.like_count or 0)
        completions = int(stats.completion_count or 0)
        skips = int(stats.skip_count or 0)

        total_plays += plays

        # Likes are the clearest signal, completions beat raw starts.
        positive_weight = plays * 1.0 + completions * 1.5 + likes * 3.0

        if positive_weight > 0:
            for family in get_track_families(track):
                family_weights[family] += positive_weight

            artist_key = _normalize_artist_key(track.artist)
            if artist_key:
                artist_weights[artist_key] += positive_weight

        interactions = plays + skips
        if skips > 0 and interactions >= MIN_INTERACTIONS_FOR_SKIP_SIGNAL:
            skip_ratio_by_track[track.id] = min(skips / interactions, 1.0)

    if not family_weights and not skip_ratio_by_track:
        return None

    max_family_weight = max(family_weights.values(), default=0.0)
    max_artist_weight = max(artist_weights.values(), default=0.0)

    return {
        "confidence": min(total_plays / CONFIDENCE_FULL_PLAYS, 1.0),
        "family_affinity": {
            family: weight / max_family_weight
            for family, weight in family_weights.items()
        }
        if max_family_weight
        else {},
        "artist_affinity": {
            artist: weight / max_artist_weight
            for artist, weight in artist_weights.items()
        }
        if max_artist_weight
        else {},
        "skip_ratio_by_track": skip_ratio_by_track,
    }


def taste_adjustment_for_candidate(
    user_taste: dict | None,
    track: Track,
    candidate_families: list[str],
) -> tuple[float, float]:
    """Returns (bonus, penalty), both ≥ 0 and already confidence-scaled."""
    if not user_taste:
        return 0.0, 0.0

    confidence = float(user_taste.get("confidence", 0.0))
    if confidence <= 0:
        return 0.0, 0.0

    family_affinity = user_taste.get("family_affinity", {})
    artist_affinity = user_taste.get("artist_affinity", {})

    family_match = max(
        (family_affinity.get(family, 0.0) for family in candidate_families),
        default=0.0,
    )
    artist_match = artist_affinity.get(_normalize_artist_key(track.artist), 0.0)

    bonus = (
        MAX_TASTE_BONUS
        * confidence
        * (0.6 * family_match + 0.4 * artist_match)
    )

    skip_ratio = user_taste.get("skip_ratio_by_track", {}).get(track.id, 0.0)
    penalty = MAX_SKIP_PENALTY * confidence * skip_ratio

    return bonus, penalty
