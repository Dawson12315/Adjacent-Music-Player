import random

from app.services.recommendations.genre_utils import get_track_families
from app.services.recommendations.reasoning import summarize_recommendation_reason
from app.services.recommendations.scoring import score_candidate


RETRIEVAL_SOURCE_WEIGHTS = {
    "genre": 0.35,
    "cooccurrence": 1.25,
    "behavior": 1.5,
}


def rank_candidates(
    candidate_tracks,
    family_counts,
    cooccurrence_scores,
    playlist_artist_counts,
    playlist_album_counts,
    retrieved_candidates=None,
    refresh: int = 0,
    playlist_id: int | None = None,
):
    scored_candidates = []
    debug_by_track_id = {}

    retrieved_candidates = retrieved_candidates or {}
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

        weighted_retrieval_score = 0.0
        for source_name, raw_score in retrieval_sources.items():
            weight = RETRIEVAL_SOURCE_WEIGHTS.get(source_name, 1.0)
            weighted_retrieval_score += raw_score * weight

        shared_families = candidate_debug.get("shared_families", [])
        has_shared_family = len(shared_families) > 0
        has_cooccurrence = retrieval_sources.get("cooccurrence", 0.0) > 0
        has_genre_signal = retrieval_sources.get("genre", 0.0) > 0

        has_alignment = has_shared_family or has_cooccurrence or has_genre_signal

        if not has_alignment and weighted_retrieval_score > 0:
            weighted_retrieval_score *= 0.35

        tie_break_jitter = rng.random() * 0.05
        final_score = base_score + weighted_retrieval_score + tie_break_jitter

        candidate_debug["base_score"] = base_score
        candidate_debug["retrieval_sources"] = retrieval_sources
        candidate_debug["retrieval_weighted_score"] = weighted_retrieval_score
        candidate_debug["tie_break_jitter"] = tie_break_jitter
        candidate_debug["final_score"] = final_score
        candidate_debug["shared_families"] = shared_families
        candidate_debug["has_alignment"] = has_alignment

        if weighted_retrieval_score > 0:
            candidate_debug.setdefault("reasons", []).append(
                f"retrieval_weighted:+{weighted_retrieval_score:.2f}"
            )

        if not has_alignment and weighted_retrieval_score > 0:
            candidate_debug.setdefault("reasons", []).append(
                "behavior_without_alignment_penalty"
            )

        candidate_debug["reason_summary"] = summarize_recommendation_reason(candidate_debug)

        if final_score <= 0:
            continue

        scored_candidates.append((final_score, track))
        debug_by_track_id[track.id] = candidate_debug

    return scored_candidates, debug_by_track_id