from typing import Tuple, List
from app.models.track import Track


def score_candidate(
    track: Track,
    candidate_families: list[str],
    family_counts: dict,
    cooccurrence_scores: dict,
    playlist_artist_counts: dict,
    playlist_album_counts: dict,
) -> Tuple[int, dict]:
    score = 0
    reasons = []

    shared_families = [
        family for family in candidate_families if family in family_counts
    ]

    if not shared_families:
        return 0, {}

    # FAMILY SCORE
    family_score = 0
    for family in shared_families:
        boost = 3 + family_counts[family]
        family_score += boost
        reasons.append(f"shared_family:{family}(+{boost})")

    score += family_score

    # COOCCURRENCE
    co_score = cooccurrence_scores.get(track.id, 0)
    co_boost = 0
    if co_score > 0:
        co_boost = co_score * 8
        score += co_boost
        reasons.append(f"cooccurrence:+{co_boost}")

    # ARTIST PENALTY
    artist_key = (track.artist or "").strip().casefold()
    artist_penalty = 0
    if artist_key and playlist_artist_counts.get(artist_key, 0) > 0:
        artist_penalty = 2
        score -= artist_penalty
        reasons.append("artist_repeat_penalty:-2")

    # ALBUM PENALTY
    album_key = f"{artist_key}::{(track.album or '').strip().casefold()}"
    album_penalty = 0
    if track.album and playlist_album_counts.get(album_key, 0) > 0:
        album_penalty = 1
        score -= album_penalty
        reasons.append("album_repeat_penalty:-1")

    # MULTI-FAMILY BONUS
    multi_family_bonus = 0
    if len(shared_families) >= 2:
        multi_family_bonus = 2
        score += multi_family_bonus
        reasons.append("multi_family_bonus:+2")

    debug = {
        "track_id": track.id,
        "title": track.title,
        "artist": track.artist,
        "candidate_families": candidate_families,
        "shared_families": shared_families,
        "family_score": family_score,
        "cooccurrence_count": co_score,
        "cooccurrence_boost": co_boost,
        "artist_penalty": artist_penalty,
        "album_penalty": album_penalty,
        "multi_family_bonus": multi_family_bonus,
        "final_score": score,
        "reasons": reasons,
    }

    return score, debug