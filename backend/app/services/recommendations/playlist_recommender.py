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




def get_playlist_recommendations_for_playlist(
    db: Session,
    playlist_id: int,
    debug: bool = False,
    refresh: int = 0,
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

    if not playlist_track_ids:
        return []

    playlist_tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(Track.id.in_(playlist_track_ids))
        .all()
    )

    genre_counts = Counter()
    family_counts = Counter()
    playlist_artist_counts = Counter()
    playlist_album_counts = Counter()

    for track in playlist_tracks:
        track_genres = get_track_genres(track)

        unique_genres = []
        for genre in track_genres:
            if genre not in unique_genres:
                unique_genres.append(genre)

        unique_families = []
        for genre in unique_genres:
            family = map_genre_to_family(genre)
            if family not in unique_families:
                unique_families.append(family)
            genre_counts[genre] += 1

        for family in unique_families:
            family_counts[family] += 1

        if track.artist:
            playlist_artist_counts[track.artist.strip().casefold()] += 1

        if track.album:
            album_key = (
                f"{(track.artist or '').strip().casefold()}::"
                f"{track.album.strip().casefold()}"
            )
            playlist_album_counts[album_key] += 1

    if not family_counts:
        return []

    playlist_debug_tracks = []
    if debug:
        for track in playlist_tracks:
            playlist_debug_tracks.append(
                {
                    "track_id": track.id,
                    "title": track.title,
                    "artist": track.artist,
                    "genres": get_track_genres(track),
                    "families": get_track_families(track),
                }
            )

    retrieved_candidates = retrieve_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        family_counts=family_counts,
        limit=400,
        refresh=refresh,
        playlist_id=playlist_id,
    )

    candidate_track_ids = list(retrieved_candidates.keys())

    if not candidate_track_ids:
        return []

    candidate_tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(Track.id.in_(candidate_track_ids))
        .all()
    )

    scored_candidates, debug_by_track_id = rank_candidates(
        candidate_tracks=candidate_tracks,
        family_counts=family_counts,
        cooccurrence_scores={},
        playlist_artist_counts=playlist_artist_counts,
        playlist_album_counts=playlist_album_counts,
        retrieved_candidates=retrieved_candidates,
        refresh=refresh,
        playlist_id=playlist_id,
    )

    if not scored_candidates:
        return []

    top_tracks = diversify_tracks(
        scored_candidates=scored_candidates,
        family_counts=family_counts,
        get_track_families=get_track_families,
        max_results=20,
        refresh=refresh,
        playlist_id=playlist_id,
    )

    if top_tracks and refresh > 0:
        shift = refresh % len(top_tracks)
        top_tracks = top_tracks[shift:] + top_tracks[:shift]

    if debug:
        return {
            "playlist_profile": {
                "playlist_track_ids": playlist_track_ids,
                "family_counts": dict(family_counts),
                "genre_counts": dict(genre_counts),
                "tracks": playlist_debug_tracks,
            },
            "retrieved_candidates": {
                track_id: candidate.source_scores
                for track_id, candidate in retrieved_candidates.items()
            },
            "recommendations": [
                {
                    "track": build_track_response(track).model_dump(),
                    "debug": debug_by_track_id.get(track.id, {}),
                }
                for track in top_tracks
            ],
        }

    return [build_track_response(track) for track in top_tracks]