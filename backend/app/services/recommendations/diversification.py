from collections import Counter
import random

from app.models.track import Track


def diversify_tracks(
    scored_candidates,
    family_counts,
    get_track_families,
    max_results=20,
    refresh: int = 0,
    playlist_id: int | None = None,
):
    artist_counts = Counter()
    album_counts = Counter()
    selected_ids = set()
    selected_family_counts = Counter()
    results = []

    total_family_weight = max(sum(family_counts.values()), 1)
    rng = random.Random(f"diversify:{playlist_id}:{refresh}")

    def can_add(track: Track):
        artist_key = (track.artist or "").strip().casefold()
        album_key = f"{artist_key}::{(track.album or '').strip().casefold()}"

        if track.id in selected_ids:
            return False

        if artist_key and artist_counts[artist_key] >= 2:
            return False

        if track.album and album_counts[album_key] >= 2:
            return False

        primary_family = best_family(track)

        if primary_family and selected_family_counts[primary_family] >= 4:
            return False

        return True

    def best_family(track: Track):
        families = get_track_families(track)
        valid = [f for f in families if f in family_counts]

        if not valid:
            return None

        return max(valid, key=lambda f: family_counts[f])

    def add(track: Track):
        artist_key = (track.artist or "").strip().casefold()
        album_key = f"{artist_key}::{(track.album or '').strip().casefold()}"
        fam = best_family(track)

        results.append(track)
        selected_ids.add(track.id)

        if artist_key:
            artist_counts[artist_key] += 1

        if track.album:
            album_counts[album_key] += 1

        if fam:
            selected_family_counts[fam] += 1

    while len(results) < max_results:
        best_candidate = None
        best_adjusted_score = None

        shuffled_candidates = list(scored_candidates)
        rng.shuffle(shuffled_candidates)

        for score, track in shuffled_candidates:
            if not can_add(track):
                continue

            families = get_track_families(track)

            diversity_penalty = 0
            diversity_bonus = 0

            for family in families:
                diversity_penalty += selected_family_counts[family] * 1.5

                desired_ratio = family_counts[family] / total_family_weight
                current_ratio = selected_family_counts[family] / max(len(results), 1)

                if current_ratio < desired_ratio:
                    diversity_bonus += 1.0

            adjusted_score = score - diversity_penalty + diversity_bonus

            if best_candidate is None or adjusted_score > best_adjusted_score:
                best_candidate = track
                best_adjusted_score = adjusted_score

        if best_candidate is None:
            break

        add(best_candidate)

    return results