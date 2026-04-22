import random

from app.services.recommendations.genre_utils import get_track_families
from app.services.recommendations.reasoning import summarize_recommendation_reason
from app.services.recommendations.scoring import score_candidate


RETRIEVAL_SOURCE_WEIGHTS = {
    "genre": 0.60,
    "cooccurrence": 0.85,
    "behavior": 0.45,
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
):
    scored_candidates = []
    debug_by_track_id = {}

    retrieved_candidates = retrieved_candidates or {}
    playlist_profile = playlist_profile or {}
    metadata_sparse = bool(playlist_profile.get("metadata_sparse"))
    unique_family_count = len(family_counts)
    focused_playlist = unique_family_count <= 2
    is_multi_cluster = bool(playlist_profile.get("is_multi_cluster"))

    rng = random.Random(f"rank:{playlist_id}:{refresh}")

    for track in candidate_tracks:
        candidate_families = get_track_families(track)

        base_score, candidate_debug = score_candidate(
            track=track,
            candidate_families=candidate_families,
            family_counts=family_counts,
            cooccurrence_scores=cooccurrence_scores,
            playlist_artist_counts=playlist_artist_counts,
            playlist_album_counts=playlist_album_counts,
        )

        retrieved = retrieved_candidates.get(track.id)
        retrieval_sources = dict(retrieved.source_scores) if retrieved else {}

        genre_source_score = retrieval_sources.get("genre", 0.0)
        cooccurrence_source_score = retrieval_sources.get("cooccurrence", 0.0)
        behavior_source_score = retrieval_sources.get("behavior", 0.0)

        content_fit_score = (
            genre_source_score * RETRIEVAL_SOURCE_WEIGHTS["genre"]
            + cooccurrence_source_score * RETRIEVAL_SOURCE_WEIGHTS["cooccurrence"]
        )
        user_affinity_score = (
            behavior_source_score * RETRIEVAL_SOURCE_WEIGHTS["behavior"]
        )

        shared_families = candidate_debug.get("shared_families", [])
        has_shared_family = len(shared_families) > 0
        has_cooccurrence = cooccurrence_source_score > 0
        has_genre_signal = genre_source_score > 0
        has_alignment = has_shared_family or has_cooccurrence or has_genre_signal

        candidate_debug["base_score"] = base_score
        candidate_debug["retrieval_sources"] = retrieval_sources
        candidate_debug["shared_families"] = shared_families
        candidate_debug["has_alignment"] = has_alignment
        candidate_debug["metadata_sparse"] = metadata_sparse
        candidate_debug["focused_playlist"] = focused_playlist
        candidate_debug["unique_family_count"] = unique_family_count
        candidate_debug["is_multi_cluster"] = is_multi_cluster

        if focused_playlist and not metadata_sparse and not has_shared_family:
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
            if user_affinity_score > 0 or has_shared_family or has_cooccurrence:
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