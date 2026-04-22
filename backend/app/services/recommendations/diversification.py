from collections import Counter
import random

from app.models.track import Track


def diversify_tracks(
    scored_candidates,
    playlist_profile,
    get_track_families,
    max_results=20,
    refresh: int = 0,
    playlist_id: int | None = None,
):
    family_counts = playlist_profile.get("family_counts", Counter())
    is_multi_cluster = bool(playlist_profile.get("is_multi_cluster", False))

    artist_counts = Counter()
    album_counts = Counter()
    selected_ids = set()
    selected_family_counts = Counter()
    selected_cluster_counts = Counter()
    results = []

    total_family_weight = max(sum(family_counts.values()), 1)
    unique_family_count = max(len(family_counts), 1)
    track_count = max(int(playlist_profile.get("track_count", 0)), 1)

    focused_playlist = unique_family_count <= 2 or track_count <= 8
    base_max_artist_repeat = 3 if focused_playlist else 2
    base_max_album_repeat = 2 if focused_playlist else 1
    base_max_family_repeat = 5 if focused_playlist else 3

    rng = random.Random(f"diversify:{playlist_id}:{refresh}")

    def unpack_candidate(entry):
        if len(entry) == 3:
            score, track, meta = entry
            return score, track, meta or {}
        score, track = entry
        return score, track, {}

    def best_family(track: Track):
        families = get_track_families(track)
        valid = [f for f in families if f in family_counts]

        if not valid:
            return None

        return max(valid, key=lambda f: family_counts[f])

    def candidate_cluster_family(meta: dict):
        cluster_families = meta.get("cluster_families", [])
        if cluster_families:
            return cluster_families[0]
        return None

    def can_add(
        track: Track,
        max_artist_repeat: int | None,
        max_album_repeat: int | None,
        max_family_repeat: int | None,
    ):
        artist_key = (track.artist or "").strip().casefold()
        album_key = f"{artist_key}::{(track.album or '').strip().casefold()}"

        if track.id in selected_ids:
            return False

        if (
            max_artist_repeat is not None
            and artist_key
            and artist_counts[artist_key] >= max_artist_repeat
        ):
            return False

        if (
            max_album_repeat is not None
            and track.album
            and album_counts[album_key] >= max_album_repeat
        ):
            return False

        primary_family = best_family(track)
        if (
            max_family_repeat is not None
            and primary_family
            and selected_family_counts[primary_family] >= max_family_repeat
        ):
            return False

        return True

    def add(track: Track, meta: dict):
        artist_key = (track.artist or "").strip().casefold()
        album_key = f"{artist_key}::{(track.album or '').strip().casefold()}"
        fam = best_family(track)
        cluster_family = candidate_cluster_family(meta)

        results.append(track)
        selected_ids.add(track.id)

        if artist_key:
            artist_counts[artist_key] += 1

        if track.album:
            album_counts[album_key] += 1

        if fam:
            selected_family_counts[fam] += 1

        if cluster_family:
            selected_cluster_counts[cluster_family] += 1

    def current_top_pool_size():
        if focused_playlist:
            return 2 if refresh > 0 else 1
        if is_multi_cluster:
            return 8 if refresh > 0 else 4
        return 5 if refresh > 0 else 3

    relaxation_passes = [
        {
            "name": "strict",
            "max_artist_repeat": base_max_artist_repeat,
            "max_album_repeat": base_max_album_repeat,
            "max_family_repeat": base_max_family_repeat,
        },
        {
            "name": "relax_album",
            "max_artist_repeat": base_max_artist_repeat,
            "max_album_repeat": None,
            "max_family_repeat": base_max_family_repeat,
        },
        {
            "name": "relax_artist_album",
            "max_artist_repeat": None,
            "max_album_repeat": None,
            "max_family_repeat": base_max_family_repeat,
        },
        {
            "name": "relax_all",
            "max_artist_repeat": None,
            "max_album_repeat": None,
            "max_family_repeat": None,
        },
    ]

    while len(results) < max_results:
        selected_entry = None

        for pass_config in relaxation_passes:
            candidate_pool = []

            shuffled_candidates = list(scored_candidates)
            rng.shuffle(shuffled_candidates)

            for entry in shuffled_candidates:
                score, track, meta = unpack_candidate(entry)

                if not can_add(
                    track=track,
                    max_artist_repeat=pass_config["max_artist_repeat"],
                    max_album_repeat=pass_config["max_album_repeat"],
                    max_family_repeat=pass_config["max_family_repeat"],
                ):
                    continue

                families = get_track_families(track)
                cluster_family = candidate_cluster_family(meta)

                diversity_penalty = 0.0
                diversity_bonus = 0.0

                for family in families:
                    family_repeat_penalty = selected_family_counts[family] * (
                        1.0 if focused_playlist else 1.5
                    )
                    diversity_penalty += family_repeat_penalty

                    desired_ratio = (
                        family_counts[family] / total_family_weight
                        if family in family_counts
                        else 0.0
                    )
                    current_ratio = selected_family_counts[family] / max(len(results), 1)

                    if desired_ratio > 0 and current_ratio < desired_ratio:
                        diversity_bonus += 0.9

                if is_multi_cluster and cluster_family:
                    if selected_cluster_counts[cluster_family] == 0:
                        diversity_bonus += 1.25
                    else:
                        diversity_bonus += max(
                            0.8 - (selected_cluster_counts[cluster_family] * 0.25),
                            0.0,
                        )

                refresh_exploration_bonus = 0.0
                if refresh > 0:
                    if is_multi_cluster:
                        refresh_exploration_bonus = rng.random() * 1.25
                    elif not focused_playlist:
                        refresh_exploration_bonus = rng.random() * 0.75
                    else:
                        refresh_exploration_bonus = rng.random() * 0.10

                relaxation_bonus = 0.0
                if pass_config["name"] == "relax_album":
                    relaxation_bonus = 0.10
                elif pass_config["name"] == "relax_artist_album":
                    relaxation_bonus = 0.20
                elif pass_config["name"] == "relax_all":
                    relaxation_bonus = 0.30

                adjusted_score = (
                    score
                    - diversity_penalty
                    + diversity_bonus
                    + refresh_exploration_bonus
                    + relaxation_bonus
                )

                candidate_pool.append((adjusted_score, track, meta))

            if not candidate_pool:
                continue

            candidate_pool.sort(key=lambda item: item[0], reverse=True)

            top_pool_size = current_top_pool_size()
            if pass_config["name"] == "relax_artist_album":
                top_pool_size = max(top_pool_size, 4 if focused_playlist else 6)
            elif pass_config["name"] == "relax_all":
                top_pool_size = max(top_pool_size, 5 if focused_playlist else 8)

            top_pool = candidate_pool[:top_pool_size]
            selected_entry = rng.choice(top_pool)
            break

        if selected_entry is None:
            break

        _selected_score, best_candidate, best_candidate_meta = selected_entry
        add(best_candidate, best_candidate_meta or {})

    return results