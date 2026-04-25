def summarize_recommendation_reason(candidate_debug: dict) -> str:
    shared_families = candidate_debug.get("shared_families", [])
    retrieval_sources = candidate_debug.get("retrieval_sources", {})

    has_behavior = retrieval_sources.get("behavior", 0) > 0
    has_cooccurrence = retrieval_sources.get("cooccurrence", 0) > 0
    has_genre = retrieval_sources.get("genre", 0) > 0
    has_lastfm_artist = retrieval_sources.get("lastfm_artist", 0) > 0

    metadata_sparse = candidate_debug.get("metadata_sparse", False)
    strong_lastfm_artist_alignment = candidate_debug.get(
        "strong_lastfm_artist_alignment",
        False,
    )

    if shared_families:
        family = shared_families[0].replace("_", " ")

        if has_lastfm_artist and has_behavior:
            return f"Similar artist match for this playlist, fits your {family} taste, and matches your recent listening"

        if has_lastfm_artist and has_cooccurrence:
            return f"Similar artist match for this playlist, fits your {family} vibe, and connects to nearby tracks"

        if has_lastfm_artist:
            return f"Similar artist match that also fits your playlist’s {family} vibe"

        if has_behavior and has_cooccurrence:
            return f"Fits your {family} vibe, your listening habits, and nearby track relationships"

        if has_behavior:
            return f"Fits your {family} taste and your recent listening"

        if has_cooccurrence:
            return f"Matches your playlist’s {family} vibe and track relationships"

        if has_genre:
            return f"Matches your playlist’s {family} vibe"

    if has_lastfm_artist:
        if strong_lastfm_artist_alignment:
            return "Recommended from a strong Last.fm similar-artist match"

        if metadata_sparse:
            return "Recommended from Last.fm similar artists because playlist genre data is limited"

        return "Recommended from Last.fm similar artists in your library"

    if has_cooccurrence and has_behavior:
        if metadata_sparse:
            return "Connected to tracks in this playlist and supported by your listening history"
        return "Matches track relationships in this playlist and your listening behavior"

    if has_cooccurrence:
        if metadata_sparse:
            return "Recommended from track relationships because playlist genre data is limited"
        return "Often appears alongside tracks like these"

    if has_behavior:
        return "Based on your recent listening behavior"

    if has_genre:
        return "Matches the overall genre mix"

    return "Recommended for this playlist"