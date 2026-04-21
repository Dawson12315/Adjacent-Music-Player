def summarize_recommendation_reason(candidate_debug: dict) -> str:
    shared_families = candidate_debug.get("shared_families", [])
    retrieval_sources = candidate_debug.get("retrieval_sources", {})

    has_behavior = retrieval_sources.get("behavior", 0) > 0
    has_cooccurrence = retrieval_sources.get("cooccurrence", 0) > 0
    has_genre = retrieval_sources.get("genre", 0) > 0

    if shared_families:
        family = shared_families[0].replace("_", " ")
        if has_behavior:
            return f"Fits your {family} taste and your recent listening"
        if has_cooccurrence:
            return f"Matches your playlist’s {family} vibe and track relationships"
        return f"Matches your playlist’s {family} vibe"

    if has_behavior:
        return "Based on your recent listening behavior"

    if has_cooccurrence:
        return "Often appears alongside tracks like these"

    if has_genre:
        return "Matches the overall genre mix"

    return "Recommended for this playlist"