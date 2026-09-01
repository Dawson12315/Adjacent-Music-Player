import random

from app.services.recommendations.genre_utils import get_track_families
from app.services.recommendations.reasoning import summarize_recommendation_reason
from app.services.recommendations.scoring import score_candidate
from app.services.recommendations.user_taste import taste_adjustment_for_candidate


# The single place channel influence is decided. Every channel's raw score is
# rank-normalized to 0–1 across the candidate set first, so these weights mean
# the same thing regardless of playlist size or how a channel scales
# internally. (Raw scales previously varied by 10x between channels, which is
# why the old constants were unexplainable.)
CHANNEL_WEIGHTS = {
    "genre": 1.0,
    "cooccurrence": 2.0,
    "behavior": 1.0,
    "lastfm_artist": 1.5,
    "lastfm_track": 2.5,
    "recent": 0.5,
}

# On the normalized 0–1 scale: a candidate in the top 40% of Last.fm artist
# matches counts as strongly aligned.
STRONG_LASTFM_ARTIST_NORM_THRESHOLD = 0.60


def rank_normalize(values_by_track: dict[int, float]) -> dict[int, float]:
    """Percentile-of-distinct-values normalization: robust to heavy tails,
    ties stay tied, output is 0–1 with the best value at 1."""
    if not values_by_track:
        return {}

    distinct_values = sorted(set(values_by_track.values()))

    if len(distinct_values) == 1:
        return {track_id: 1.0 for track_id in values_by_track}

    position = {value: index for index, value in enumerate(distinct_values)}
    top = len(distinct_values) - 1

    return {
        track_id: position[value] / top
        for track_id, value in values_by_track.items()
    }


def normalize_channels(retrieved_candidates: dict) -> dict[str, dict[int, float]]:
    raw_by_channel: dict[str, dict[int, float]] = {}

    for track_id, candidate in retrieved_candidates.items():
        for source_name, score in candidate.source_scores.items():
            raw_by_channel.setdefault(source_name, {})[track_id] = score

    return {
        source_name: rank_normalize(values)
        for source_name, values in raw_by_channel.items()
    }


def rank_candidates(
    candidate_tracks,
    family_counts,
    cooccurrence_scores,
    playlist_artist_counts,
    playlist_album_counts,
    retrieved_candidates=None,
    playlist_profile=None,
    refresh: int = 0,
    playlist_id: int | None = None,
    user_taste: dict | None = None,
):
    scored_candidates = []
    debug_by_track_id = {}

    retrieved_candidates = retrieved_candidates or {}
    playlist_profile = playlist_profile or {}
    metadata_sparse = bool(playlist_profile.get("metadata_sparse"))
    unique_family_count = len(family_counts)
    focused_playlist = bool(
        playlist_profile.get("focused_playlist", unique_family_count <= 2)
    )
    is_multi_cluster = bool(playlist_profile.get("is_multi_cluster"))

    normalized_channels = normalize_channels(retrieved_candidates)

    rng = random.Random(f"rank:{playlist_id}:{refresh}")

    for track in candidate_tracks:
        candidate_families = get_track_families(track)

        retrieved = retrieved_candidates.get(track.id)
        retrieval_sources = dict(retrieved.source_scores) if retrieved else {}

        base_score, candidate_debug = score_candidate(
            track=track,
            candidate_families=candidate_families,
            family_counts=family_counts,
            cooccurrence_scores=cooccurrence_scores,
            playlist_artist_counts=playlist_artist_counts,
            playlist_album_counts=playlist_album_counts,
            retrieved_source_scores=retrieval_sources,
        )

        normalized = {
            source_name: normalized_channels.get(source_name, {}).get(track.id, 0.0)
            for source_name in CHANNEL_WEIGHTS
        }

        strong_lastfm_artist_alignment = (
            normalized["lastfm_artist"] >= STRONG_LASTFM_ARTIST_NORM_THRESHOLD
            and retrieval_sources.get("lastfm_artist", 0.0) > 0
        )

        content_fit_score = (
            normalized["genre"] * CHANNEL_WEIGHTS["genre"]
            + normalized["cooccurrence"] * CHANNEL_WEIGHTS["cooccurrence"]
            + normalized["lastfm_artist"] * CHANNEL_WEIGHTS["lastfm_artist"]
            + normalized["lastfm_track"] * CHANNEL_WEIGHTS["lastfm_track"]
            + normalized["recent"] * CHANNEL_WEIGHTS["recent"]
        )

        user_affinity_score = normalized["behavior"] * CHANNEL_WEIGHTS["behavior"]

        # Bounded, confidence-scaled personal taste (see user_taste.py).
        taste_bonus, skip_penalty = taste_adjustment_for_candidate(
            user_taste, track, candidate_families
        )
        user_affinity_score += taste_bonus

        shared_families = candidate_debug.get("shared_families", [])
        has_shared_family = len(shared_families) > 0
        has_cooccurrence = retrieval_sources.get("cooccurrence", 0.0) > 0
        has_genre_signal = retrieval_sources.get("genre", 0.0) > 0
        has_lastfm_artist_signal = retrieval_sources.get("lastfm_artist", 0.0) > 0
        has_lastfm_track_signal = retrieval_sources.get("lastfm_track", 0.0) > 0

        has_alignment = (
            has_shared_family
            or has_cooccurrence
            or has_genre_signal
            or has_lastfm_artist_signal
            or has_lastfm_track_signal
        )

        candidate_debug["base_score"] = base_score
        candidate_debug["retrieval_sources"] = retrieval_sources
        candidate_debug["normalized_sources"] = normalized
        candidate_debug["shared_families"] = shared_families
        candidate_debug["has_alignment"] = has_alignment
        candidate_debug["metadata_sparse"] = metadata_sparse
        candidate_debug["focused_playlist"] = focused_playlist
        candidate_debug["unique_family_count"] = unique_family_count
        candidate_debug["is_multi_cluster"] = is_multi_cluster
        candidate_debug["strong_lastfm_artist_alignment"] = strong_lastfm_artist_alignment
        candidate_debug["taste_bonus"] = taste_bonus
        candidate_debug["skip_penalty"] = skip_penalty

        if focused_playlist and not metadata_sparse and not has_shared_family:
            if strong_lastfm_artist_alignment or has_lastfm_track_signal:
                candidate_debug.setdefault("reasons", []).append(
                    "focused_playlist_lastfm_alignment_override"
                )
                content_fit_score *= 0.65
            else:
                candidate_debug.setdefault("reasons", []).append(
                    "focused_playlist_family_hard_gate"
                )
                candidate_debug["content_fit_score"] = 0.0
                candidate_debug["user_affinity_score"] = 0.0
                candidate_debug["retrieval_weighted_score"] = 0.0
                candidate_debug["refresh_exploration_bonus"] = 0.0
                candidate_debug["tie_break_jitter"] = 0.0
                candidate_debug["final_score"] = float("-inf")
                candidate_debug["reason_summary"] = summarize_recommendation_reason(candidate_debug)
                continue

        if not has_shared_family:
            if focused_playlist:
                if user_affinity_score > 0:
                    user_affinity_score *= 0.05

                if strong_lastfm_artist_alignment or has_lastfm_track_signal:
                    candidate_debug.setdefault("reasons", []).append(
                        "focused_playlist_lastfm_soft_penalty"
                    )
                else:
                    if content_fit_score > 0:
                        content_fit_score *= 0.10
                    candidate_debug.setdefault("reasons", []).append(
                        "focused_playlist_genre_strict_penalty"
                    )
            else:
                if not has_alignment and user_affinity_score > 0:
                    if is_multi_cluster:
                        user_affinity_score *= 0.75
                        candidate_debug.setdefault("reasons", []).append(
                            "multi_cluster_behavior_tolerance"
                        )
                    else:
                        user_affinity_score *= 0.25
                        candidate_debug.setdefault("reasons", []).append(
                            "behavior_without_alignment_penalty"
                        )

        if metadata_sparse and has_cooccurrence:
            content_fit_score += 1.0
            candidate_debug.setdefault("reasons", []).append(
                "metadata_sparse_cooccurrence_bonus:+1.00"
            )

        cluster_survival_bonus = 0.0
        if is_multi_cluster and not focused_playlist:
            if user_affinity_score > 0 or has_shared_family or has_cooccurrence or has_lastfm_track_signal:
                cluster_survival_bonus = 0.50
                candidate_debug.setdefault("reasons", []).append(
                    "multi_cluster_survival_bonus:+0.50"
                )

        refresh_exploration_bonus = 0.0
        if refresh > 0:
            if focused_playlist:
                refresh_exploration_bonus = rng.random() * 0.08
            elif is_multi_cluster:
                refresh_exploration_bonus = rng.random() * 0.90
            else:
                refresh_exploration_bonus = rng.random() * 0.45

            if refresh_exploration_bonus > 0:
                candidate_debug.setdefault("reasons", []).append(
                    f"refresh_exploration_bonus:+{refresh_exploration_bonus:.2f}"
                )

        retrieval_weighted_score = (
            content_fit_score
            + user_affinity_score
            + cluster_survival_bonus
            + refresh_exploration_bonus
            - skip_penalty
        )

        if taste_bonus > 0:
            candidate_debug.setdefault("reasons", []).append(
                f"user_taste_bonus:+{taste_bonus:.2f}"
            )
        if skip_penalty > 0:
            candidate_debug.setdefault("reasons", []).append(
                f"user_skip_penalty:-{skip_penalty:.2f}"
            )

        tie_break_jitter = rng.random() * (0.03 if focused_playlist else 0.10)
        final_score = base_score + retrieval_weighted_score + tie_break_jitter

        candidate_debug["content_fit_score"] = content_fit_score
        candidate_debug["user_affinity_score"] = user_affinity_score
        candidate_debug["cluster_survival_bonus"] = cluster_survival_bonus
        candidate_debug["refresh_exploration_bonus"] = refresh_exploration_bonus
        candidate_debug["retrieval_weighted_score"] = retrieval_weighted_score
        candidate_debug["tie_break_jitter"] = tie_break_jitter
        candidate_debug["final_score"] = final_score

        if retrieval_weighted_score > 0:
            candidate_debug.setdefault("reasons", []).append(
                f"retrieval_weighted:+{retrieval_weighted_score:.2f}"
            )

        candidate_debug["reason_summary"] = summarize_recommendation_reason(candidate_debug)

        if final_score <= 0:
            continue

        scored_candidates.append((final_score, track))
        debug_by_track_id[track.id] = candidate_debug

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    return scored_candidates, debug_by_track_id
