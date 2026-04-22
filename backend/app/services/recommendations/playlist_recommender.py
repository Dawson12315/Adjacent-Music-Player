from collections import Counter

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.models.playlist import Playlist
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.services.recommendations.diversification import diversify_tracks
from app.services.recommendations.genre_utils import (
    get_track_families,
    get_track_genres,
    map_genre_to_family,
)
from app.services.recommendations.ranking import rank_candidates
from app.services.recommendations.retrieval import retrieve_candidates
from app.services.recommendations.utils import build_track_response


def _normalize_artist_key(value: str | None) -> str:
    return (value or "").strip().casefold()


def _normalize_album_key(track: Track) -> str:
    artist_key = _normalize_artist_key(track.artist)
    album_key = (track.album or "").strip().casefold()
    return f"{artist_key}::{album_key}"


def _serialize_playlist_profile(
    playlist_profile: dict,
    seed_track_ids: list[int],
    exclude_track_ids: list[int],
) -> dict:
    return {
        "playlist_track_ids": seed_track_ids,
        "track_count": playlist_profile["track_count"],
        "family_counts": dict(playlist_profile["family_counts"]),
        "genre_counts": dict(playlist_profile["genre_counts"]),
        "primary_families": playlist_profile["primary_families"],
        "metadata_sparse": playlist_profile["metadata_sparse"],
        "focused_playlist": playlist_profile["focused_playlist"],
        "dominant_family_share": playlist_profile["dominant_family_share"],
        "is_multi_cluster": playlist_profile["is_multi_cluster"],
        "excluded_track_ids": exclude_track_ids,
        "tracks": playlist_profile["tracks"],
    }


def build_playlist_profile(playlist_tracks: list[Track]) -> dict:
    genre_counts = Counter()
    family_counts = Counter()
    artist_counts = Counter()
    album_counts = Counter()
    playlist_debug_tracks = []

    for track in playlist_tracks:
        track_genres = get_track_genres(track)
        normalized_unique_genres: list[str] = []
        seen_genres = set()

        for genre in track_genres:
            normalized = genre.strip()
            normalized_key = normalized.casefold()
            if not normalized or normalized_key in seen_genres:
                continue

            seen_genres.add(normalized_key)
            normalized_unique_genres.append(normalized)

        unique_families: list[str] = []
        seen_families = set()

        for genre in normalized_unique_genres:
            family = map_genre_to_family(genre)
            genre_counts[genre] += 1

            if family in seen_families:
                continue

            seen_families.add(family)
            unique_families.append(family)
            family_counts[family] += 1

        artist_key = _normalize_artist_key(track.artist)
        if artist_key:
            artist_counts[artist_key] += 1

        album_key = _normalize_album_key(track)
        if track.album and album_key:
            album_counts[album_key] += 1

        playlist_debug_tracks.append(
            {
                "track_id": track.id,
                "title": track.title,
                "artist": track.artist,
                "album": track.album,
                "genres": get_track_genres(track),
                "families": get_track_families(track),
            }
        )

    primary_families = [family for family, _count in family_counts.most_common(5)]
    track_count = len(playlist_tracks)
    metadata_sparse = len(family_counts) == 0
    focused_playlist = len(family_counts) <= 2 if family_counts else False

    family_count_values = [count for _family, count in family_counts.most_common(5)]
    dominant_family_share = 0.0
    if family_count_values:
        dominant_family_share = max(family_count_values) / max(sum(family_count_values), 1)

    is_multi_cluster = (
        not metadata_sparse
        and not focused_playlist
        and len(family_count_values) >= 3
        and dominant_family_share < 0.50
    )

    return {
        "track_ids": [track.id for track in playlist_tracks],
        "track_count": track_count,
        "genre_counts": genre_counts,
        "family_counts": family_counts,
        "artist_counts": artist_counts,
        "album_counts": album_counts,
        "primary_families": primary_families,
        "metadata_sparse": metadata_sparse,
        "focused_playlist": focused_playlist,
        "dominant_family_share": dominant_family_share,
        "is_multi_cluster": is_multi_cluster,
        "tracks": playlist_debug_tracks,
    }


def _retrieve_and_rank_candidates(
    db: Session,
    seed_track_ids: list[int],
    playlist_profile: dict,
    refresh: int,
    playlist_id: int | None,
    retrieval_limit: int,
):
    retrieved_candidates = retrieve_candidates(
        db=db,
        playlist_track_ids=seed_track_ids,
        playlist_profile=playlist_profile,
        limit=retrieval_limit,
        refresh=refresh,
        playlist_id=playlist_id,
    )

    candidate_track_ids = list(retrieved_candidates.keys())
    if not candidate_track_ids:
        return [], {}, {}

    candidate_tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(Track.id.in_(candidate_track_ids))
        .all()
    )

    cooccurrence_scores = {
        track_id: candidate.source_scores.get("cooccurrence", 0.0)
        for track_id, candidate in retrieved_candidates.items()
    }

    scored_candidates, debug_by_track_id = rank_candidates(
        candidate_tracks=candidate_tracks,
        family_counts=playlist_profile["family_counts"],
        cooccurrence_scores=cooccurrence_scores,
        playlist_artist_counts=playlist_profile["artist_counts"],
        playlist_album_counts=playlist_profile["album_counts"],
        retrieved_candidates=retrieved_candidates,
        playlist_profile=playlist_profile,
        refresh=refresh,
        playlist_id=playlist_id,
    )

    return scored_candidates, debug_by_track_id, retrieved_candidates


def _build_family_clusters(
    playlist_tracks: list[Track],
    playlist_profile: dict,
) -> list[dict]:
    if not playlist_profile.get("is_multi_cluster", False):
        return []

    family_counts = playlist_profile["family_counts"]
    cluster_families = [
        family
        for family, count in family_counts.most_common(4)
        if count >= 2
    ]

    clusters = []
    for family in cluster_families:
        cluster_tracks = [
            track
            for track in playlist_tracks
            if family in get_track_families(track)
        ]

        if len(cluster_tracks) < 2:
            continue

        cluster_profile = build_playlist_profile(cluster_tracks)
        cluster_profile["cluster_family"] = family
        cluster_profile["is_multi_cluster"] = False
        cluster_profile["focused_playlist"] = len(cluster_profile["family_counts"]) <= 2

        clusters.append(
            {
                "family": family,
                "tracks": cluster_tracks,
                "track_ids": [track.id for track in cluster_tracks],
                "profile": cluster_profile,
            }
        )

    return clusters


def _merge_clustered_candidates(
    global_scored_candidates,
    cluster_candidate_groups,
):
    merged: dict[int, dict] = {}

    def _upsert(score, track, meta):
        existing = merged.get(track.id)

        if not existing:
            merged[track.id] = {
                "score": score,
                "track": track,
                "meta": {
                    "cluster_families": set(meta.get("cluster_families", [])),
                    "candidate_origin": meta.get("candidate_origin", "global"),
                },
            }
            return

        if score > existing["score"]:
            existing["score"] = score
            existing["track"] = track

        existing["meta"]["cluster_families"].update(meta.get("cluster_families", []))
        if existing["meta"].get("candidate_origin") != "cluster":
            existing["meta"]["candidate_origin"] = meta.get(
                "candidate_origin",
                existing["meta"].get("candidate_origin", "global"),
            )

    for score, track in global_scored_candidates:
        _upsert(
            score,
            track,
            {
                "cluster_families": [],
                "candidate_origin": "global",
            },
        )

    for cluster_group in cluster_candidate_groups:
        family = cluster_group["family"]
        scored_candidates = cluster_group["scored_candidates"]

        for rank_index, (score, track) in enumerate(scored_candidates[:40]):
            cluster_bonus = 1.0 - (rank_index * 0.02)
            cluster_bonus = max(cluster_bonus, 0.15)

            _upsert(
                score + cluster_bonus,
                track,
                {
                    "cluster_families": [family],
                    "candidate_origin": "cluster",
                },
            )

    merged_rows = []
    for item in merged.values():
        cluster_count_bonus = 0.6 * max(len(item["meta"]["cluster_families"]) - 1, 0)
        final_score = item["score"] + cluster_count_bonus

        merged_rows.append(
            (
                final_score,
                item["track"],
                {
                    "cluster_families": sorted(item["meta"]["cluster_families"]),
                    "candidate_origin": item["meta"]["candidate_origin"],
                },
            )
        )

    merged_rows.sort(key=lambda entry: entry[0], reverse=True)
    return merged_rows


def get_playlist_recommendations_from_track_ids(
    db: Session,
    seed_track_ids: list[int],
    debug: bool = False,
    refresh: int = 0,
    playlist_id: int | None = None,
    limit: int = 20,
    exclude_track_ids: list[int] | None = None,
):
    if not seed_track_ids:
        return []

    exclude_track_ids = list(dict.fromkeys(exclude_track_ids or []))

    playlist_tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(Track.id.in_(seed_track_ids))
        .all()
    )

    if not playlist_tracks:
        return []

    playlist_profile = build_playlist_profile(playlist_tracks)

    global_scored_candidates, global_debug_by_track_id, global_retrieved_candidates = (
        _retrieve_and_rank_candidates(
            db=db,
            seed_track_ids=seed_track_ids,
            playlist_profile=playlist_profile,
            refresh=refresh,
            playlist_id=playlist_id,
            retrieval_limit=max(limit * 20, 200),
        )
    )

    cluster_debug = []
    cluster_candidate_groups = []

    if playlist_profile.get("is_multi_cluster", False):
        clusters = _build_family_clusters(
            playlist_tracks=playlist_tracks,
            playlist_profile=playlist_profile,
        )

        for cluster in clusters:
            cluster_scored_candidates, cluster_debug_by_track_id, cluster_retrieved_candidates = (
                _retrieve_and_rank_candidates(
                    db=db,
                    seed_track_ids=cluster["track_ids"],
                    playlist_profile=cluster["profile"],
                    refresh=refresh,
                    playlist_id=playlist_id,
                    retrieval_limit=max(limit * 10, 100),
                )
            )

            if not cluster_scored_candidates:
                cluster_debug.append(
                    {
                        "family": cluster["family"],
                        "seed_track_ids": cluster["track_ids"],
                        "retrieved_candidates": {},
                        "recommendations": [],
                    }
                )
                continue

            cluster_candidate_groups.append(
                {
                    "family": cluster["family"],
                    "scored_candidates": cluster_scored_candidates,
                }
            )

            if debug:
                cluster_debug.append(
                    {
                        "family": cluster["family"],
                        "seed_track_ids": cluster["track_ids"],
                        "retrieved_candidates": {
                            track_id: candidate.source_scores
                            for track_id, candidate in cluster_retrieved_candidates.items()
                        },
                        "recommendations": [
                            {
                                "track_id": track.id,
                                "title": track.title,
                                "score": score,
                                "debug": cluster_debug_by_track_id.get(track.id, {}),
                            }
                            for score, track in cluster_scored_candidates[:10]
                        ],
                    }
                )

    if playlist_profile.get("is_multi_cluster", False) and cluster_candidate_groups:
        merged_scored_candidates = _merge_clustered_candidates(
            global_scored_candidates=global_scored_candidates,
            cluster_candidate_groups=cluster_candidate_groups,
        )
    else:
        merged_scored_candidates = [
            (score, track, {"cluster_families": [], "candidate_origin": "global"})
            for score, track in global_scored_candidates
        ]

    filtered_scored_candidates = []
    seen_candidate_ids = set()

    for score, track, meta in merged_scored_candidates:
        if track.id in exclude_track_ids:
            continue
        if track.id in seed_track_ids:
            continue
        if track.id in seen_candidate_ids:
            continue

        seen_candidate_ids.add(track.id)
        filtered_scored_candidates.append((score, track, meta))

    if not filtered_scored_candidates:
        if debug:
            return {
                "playlist_profile": _serialize_playlist_profile(
                    playlist_profile=playlist_profile,
                    seed_track_ids=seed_track_ids,
                    exclude_track_ids=exclude_track_ids,
                ),
                "retrieved_candidates": {
                    track_id: candidate.source_scores
                    for track_id, candidate in global_retrieved_candidates.items()
                },
                "clusters": cluster_debug,
                "recommendations": [],
            }
        return []

    top_tracks = diversify_tracks(
        scored_candidates=filtered_scored_candidates,
        playlist_profile=playlist_profile,
        get_track_families=get_track_families,
        max_results=limit,
        refresh=refresh,
        playlist_id=playlist_id,
    )

    if (
        top_tracks
        and refresh > 0
        and not playlist_profile.get("focused_playlist", False)
        and not playlist_profile.get("is_multi_cluster", False)
    ):
        shift = refresh % len(top_tracks)
        top_tracks = top_tracks[shift:] + top_tracks[:shift]

    if debug:
        recommendation_payload = []
        for track in top_tracks:
            track_debug = dict(global_debug_by_track_id.get(track.id, {}))
            merged_meta = next(
                (
                    meta
                    for _score, candidate_track, meta in filtered_scored_candidates
                    if candidate_track.id == track.id
                ),
                {},
            )
            if merged_meta:
                track_debug["cluster_families"] = merged_meta.get("cluster_families", [])
                track_debug["candidate_origin"] = merged_meta.get("candidate_origin", "global")

            recommendation_payload.append(
                {
                    "track": build_track_response(track).model_dump(),
                    "debug": track_debug,
                }
            )

        return {
            "playlist_profile": _serialize_playlist_profile(
                playlist_profile=playlist_profile,
                seed_track_ids=seed_track_ids,
                exclude_track_ids=exclude_track_ids,
            ),
            "retrieved_candidates": {
                track_id: candidate.source_scores
                for track_id, candidate in global_retrieved_candidates.items()
            },
            "clusters": cluster_debug,
            "recommendations": recommendation_payload,
        }

    return [build_track_response(track) for track in top_tracks]


def get_playlist_recommendations_for_playlist(
    db: Session,
    playlist_id: int,
    debug: bool = False,
    refresh: int = 0,
    limit: int = 20,
    exclude_track_ids: list[int] | None = None,
):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    playlist_track_rows = (
        db.query(PlaylistTrack)
        .filter(PlaylistTrack.playlist_id == playlist_id)
        .order_by(PlaylistTrack.position.asc())
        .all()
    )

    playlist_track_ids = [row.track_id for row in playlist_track_rows]

    return get_playlist_recommendations_from_track_ids(
        db=db,
        seed_track_ids=playlist_track_ids,
        debug=debug,
        refresh=refresh,
        playlist_id=playlist_id,
        limit=limit,
        exclude_track_ids=exclude_track_ids,
    )