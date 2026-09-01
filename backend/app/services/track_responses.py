"""One place that turns Track rows into TrackResponse payloads.

Three near-identical builders had grown in the tracks, artists, and albums
routes — and two of them looked artwork up per track, so a 432-track artist
page cost 864 queries. This module batches artwork resolution into two IN
queries per request and gives every route the same response shape.
"""

from sqlalchemy.orm import Session

from app.models.album_artwork import AlbumArtwork
from app.models.artist_artwork import ArtistArtwork
from app.models.track import Track
from app.schemas.track import TrackResponse
from app.utils.artist_normalization import normalize_artist_name

# Stays under SQLite's bound-parameter ceiling.
_IN_CHUNK_SIZE = 500


def normalize_album_key(album_name: str | None) -> str:
    return " ".join((album_name or "").strip().casefold().split())


def get_artwork_maps(
    db: Session, tracks: list[Track]
) -> tuple[dict[str, str], dict[str, str]]:
    """(album_key -> path, artist_key -> path) for exactly the keys needed."""
    album_keys = {
        key
        for key in (normalize_album_key(track.album) for track in tracks)
        if key
    }
    artist_keys = {
        key
        for key in (normalize_artist_name(track.artist) for track in tracks)
        if key
    }

    album_map: dict[str, str] = {}
    artist_map: dict[str, str] = {}

    album_key_list = list(album_keys)
    for start in range(0, len(album_key_list), _IN_CHUNK_SIZE):
        chunk = album_key_list[start : start + _IN_CHUNK_SIZE]
        for row in (
            db.query(AlbumArtwork.album_key, AlbumArtwork.artwork_path)
            .filter(AlbumArtwork.album_key.in_(chunk))
            .all()
        ):
            if row.artwork_path:
                album_map[row.album_key] = row.artwork_path

    artist_key_list = list(artist_keys)
    for start in range(0, len(artist_key_list), _IN_CHUNK_SIZE):
        chunk = artist_key_list[start : start + _IN_CHUNK_SIZE]
        for row in (
            db.query(ArtistArtwork.artist_key, ArtistArtwork.artwork_path)
            .filter(ArtistArtwork.artist_key.in_(chunk))
            .all()
        ):
            if row.artwork_path:
                artist_map[row.artist_key] = row.artwork_path

    return album_map, artist_map


def build_track_response_from_maps(
    track: Track,
    album_map: dict[str, str],
    artist_map: dict[str, str],
) -> TrackResponse:
    album_artwork_path = album_map.get(normalize_album_key(track.album))
    artist_artwork_path = artist_map.get(normalize_artist_name(track.artist))

    return TrackResponse(
        id=track.id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        genre=track.genre,
        genres=[item.genre for item in track.track_genres if item.genre],
        artists=[item.artist_name for item in track.track_artists if item.artist_name],
        file_path=track.file_path,
        artwork_path=album_artwork_path,
        album_artwork_path=album_artwork_path,
        artist_artwork_path=artist_artwork_path,
        raw_title=track.raw_title,
        raw_artist=track.raw_artist,
        raw_album=track.raw_album,
        raw_genre=track.raw_genre,
        musicbrainz_recording_id=track.musicbrainz_recording_id,
        lastfm_tags_enriched=track.lastfm_tags_enriched,
        duration_seconds=track.duration_seconds,
    )


def build_track_responses(db: Session, tracks: list[Track]) -> list[TrackResponse]:
    if not tracks:
        return []

    album_map, artist_map = get_artwork_maps(db, tracks)
    return [
        build_track_response_from_maps(track, album_map, artist_map)
        for track in tracks
    ]


def build_single_track_response(db: Session, track: Track) -> TrackResponse:
    return build_track_responses(db, [track])[0]
