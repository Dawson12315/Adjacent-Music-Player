from typing import Tuple

from app.models.track import Track


STRONG_LASTFM_ARTIST_BRIDGE_THRESHOLD = 1.20


def score_candidate(
    track: Track,
    candidate_families: list[str],
    family_counts: dict,
    cooccurrence_scores: dict,
    playlist_artist_counts: dict,
    playlist_album_counts: dict,
    retrieved_source_scores: dict | None = None,
) -> Tuple[float, dict]:
    score = 0.0
    reasons: list[str] = []
    retrieved_source_scores = retrieved_source_scores or {}

    shared_families = [
        family for family in candidate_families if family in family_counts
    ]

    lastfm_artist_score = float(retrieved_source_scores.get("lastfm_artist", 0.0) or 0.0)
    lastfm_track_score = float(retrieved_source_scores.get("lastfm_track", 0.0) or 0.0)

    strong_lastfm_artist_bridge = (
        lastfm_artist_score >= STRONG_LASTFM_ARTIST_BRIDGE_THRESHOLD
    )

    # --- FAMILY SCORING ---
    family_score = 0.0
    for family in shared_families:
        boost = 2.5 + (float(family_counts[family]) * 0.9)
        family_score += boost
        reasons.append(f"shared_family:{family}(+{boost:.2f})")

    score += family_score

    # --- COOCCURRENCE ---
    co_score = float(cooccurrence_scores.get(track.id, 0.0) or 0.0)
    co_boost = 0.0
    if co_score > 0:
        co_boost = co_score * 4.0
        score += co_boost
        reasons.append(f"cooccurrence:+{co_boost:.2f}")

    # --- ARTIST / ALBUM REPETITION ---
    artist_key = (track.artist or "").strip().casefold()
    album_key = f"{artist_key}::{(track.album or '').strip().casefold()}"

    artist_repeat_count = int(playlist_artist_counts.get(artist_key, 0) or 0)
    album_repeat_count = int(playlist_album_counts.get(album_key, 0) or 0)

    artist_penalty = 0.0
    if artist_repeat_count > 0:
        artist_penalty = 1.25 + (artist_repeat_count - 1) * 0.75
        score -= artist_penalty
        reasons.append(f"artist_repeat_penalty:-{artist_penalty:.2f}")

    album_penalty = 0.0
    if track.album and album_repeat_count > 0:
        album_penalty = 1.00 + (album_repeat_count - 1) * 0.50
        score -= album_penalty
        reasons.append(f"album_repeat_penalty:-{album_penalty:.2f}")

    # --- MULTI FAMILY BONUS ---
    multi_family_bonus = 0.0
    if len(shared_families) >= 2:
        multi_family_bonus = 1.5
        score += multi_family_bonus
        reasons.append(f"multi_family_bonus:+{multi_family_bonus:.2f}")

    # --- BRIDGING LOGIC ---
    bridge_bonus = 0.0
    if not shared_families:
        if co_score > 0:
            bridge_bonus = 1.5
            score += bridge_bonus
            reasons.append(f"cooccurrence_bridge_bonus:+{bridge_bonus:.2f}")
        elif strong_lastfm_artist_bridge:
            bridge_bonus = 2.25
            score += bridge_bonus
            reasons.append(f"lastfm_artist_bridge_bonus:+{bridge_bonus:.2f}")
        elif lastfm_track_score > 0:
            bridge_bonus = 2.75
            score += bridge_bonus
            reasons.append(f"lastfm_track_bridge_bonus:+{bridge_bonus:.2f}")

    # --- NO ALIGNMENT PENALTY ---
    no_alignment_penalty = 0.0
    if (
        not shared_families
        and co_score <= 0
        and not strong_lastfm_artist_bridge
        and lastfm_track_score <= 0
    ):
        no_alignment_penalty = 2.5
        score -= no_alignment_penalty
        reasons.append(f"no_alignment_penalty:-{no_alignment_penalty:.2f}")

    # --- DEBUG ---
    debug = {
        "track_id": track.id,
        "title": track.title,
        "artist": track.artist,
        "candidate_families": candidate_families,
        "shared_families": shared_families,
        "lastfm_artist_score": lastfm_artist_score,
        "lastfm_track_score": lastfm_track_score,
        "strong_lastfm_artist_bridge": strong_lastfm_artist_bridge,
        "family_score": family_score,
        "cooccurrence_count": co_score,
        "cooccurrence_boost": co_boost,
        "artist_repeat_count": artist_repeat_count,
        "album_repeat_count": album_repeat_count,
        "artist_penalty": artist_penalty,
        "album_penalty": album_penalty,
        "multi_family_bonus": multi_family_bonus,
        "bridge_bonus": bridge_bonus,
        "no_alignment_penalty": no_alignment_penalty,
        "base_score": score,
        "reasons": reasons,
    }

    return score, debug