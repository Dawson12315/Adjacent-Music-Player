from typing import Tuple

from app.models.track import Track


STRONG_LASTFM_ARTIST_BRIDGE_THRESHOLD = 1.20
# Raw cosine in the map at which a candidate with no shared family is
# bridged anyway: the map saying "near" outranks the label saying "other".
VECTOR_BRIDGE_COSINE = 0.50
# When the map knows a candidate, the family label is a coarse version of
# the same information and speaks accordingly: at or above ALIGNED the
# candidate earns a bonus that grows with nearness; below FAR the shared-
# family score is cut to FAR_FACTOR of itself (with `map_strength` 1.0 —
# the radio; playlists ask for half, and keep more of their old shape).
VECTOR_ALIGNED_COSINE = 0.45
VECTOR_FAR_COSINE = 0.25
MAP_FAR_FACTOR = 0.3
MAP_BONUS_SCALE = 1.5


def score_candidate(
    track: Track,
    candidate_families: list[str],
    family_counts: dict,
    cooccurrence_scores: dict,
    playlist_artist_counts: dict,
    playlist_album_counts: dict,
    retrieved_source_scores: dict | None = None,
    map_strength: float = 0.5,
    known_artist_map_share: float = 1.0,
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
    vector_fit = retrieved_source_scores.get("vector")
    vector_bridge = vector_fit is not None and float(vector_fit) >= VECTOR_BRIDGE_COSINE

    artist_key = (track.artist or "").strip().casefold()
    album_key = f"{artist_key}::{(track.album or '').strip().casefold()}"
    artist_repeat_count = int(playlist_artist_counts.get(artist_key, 0) or 0)
    album_repeat_count = int(playlist_album_counts.get(album_key, 0) or 0)

    # --- FAMILY SCORING ---
    family_score = 0.0
    for family in shared_families:
        boost = 2.5 + (float(family_counts[family]) * 0.9)
        family_score += boost
        reasons.append(f"shared_family:{family}(+{boost:.2f})")

    # --- THE MAP'S WORD ON THE LABEL ---
    # One family's worth, at the profile's own scale, is what nearness is
    # measured in: a near candidate gains up to one and a half of it, a far
    # one keeps a fraction of its label score however many families it
    # shares. This is what stops a seed track tagged house, pop and R&B
    # from handing its station every R&B track with a "dance" tag.
    map_bonus = 0.0
    map_factor = 1.0
    if vector_fit is not None and map_strength > 0:
        fit = float(vector_fit)
        family_unit = 2.5 + 0.9 * float(max(family_counts.values(), default=0))
        if fit >= VECTOR_ALIGNED_COSINE:
            map_bonus = fit * family_unit * MAP_BONUS_SCALE * map_strength
            # A playlist's suggestions are for finding what is not in it:
            # an artist already there keeps only a share of the map's
            # bonus, so a near new artist comes before a near known one.
            if artist_repeat_count > 0 and known_artist_map_share < 1.0:
                map_bonus *= known_artist_map_share
                reasons.append(f"known_artist_map_share:x{known_artist_map_share:.2f}")
            reasons.append(f"map_near_bonus:+{map_bonus:.2f}")
        else:
            nearness = max(0.0, (fit - VECTOR_FAR_COSINE) / (VECTOR_ALIGNED_COSINE - VECTOR_FAR_COSINE))
            floor = 1.0 - (1.0 - MAP_FAR_FACTOR) * map_strength
            map_factor = floor + (1.0 - floor) * nearness
            if family_score > 0 and map_factor < 1.0:
                reasons.append(f"map_far_family_factor:x{map_factor:.2f}")
        family_score *= map_factor

    score += family_score + map_bonus

    # --- COOCCURRENCE ---
    # Magnitude now flows exclusively through the rank-normalized channel
    # weight in ranking.py; adding co_score * 4.0 here as well double-counted
    # the signal on an unbounded scale. Presence still drives bridge logic.
    co_score = float(cooccurrence_scores.get(track.id, 0.0) or 0.0)
    co_boost = 0.0

    # --- ARTIST / ALBUM REPETITION (penalties below; the counts are read by the map block too) ---

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
        elif vector_bridge:
            bridge_bonus = 2.5
            score += bridge_bonus
            reasons.append(f"vector_bridge_bonus:+{bridge_bonus:.2f}")

    # --- NO ALIGNMENT PENALTY ---
    no_alignment_penalty = 0.0
    if (
        not shared_families
        and co_score <= 0
        and not strong_lastfm_artist_bridge
        and lastfm_track_score <= 0
        and not vector_bridge
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
        "vector_fit": vector_fit,
        "vector_bridge": vector_bridge,
        "map_bonus": map_bonus,
        "map_factor": map_factor,
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