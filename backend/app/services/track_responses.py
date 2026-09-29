"""One place that turns Track rows into TrackResponse payloads.

Three near-identical builders had grown in the tracks, artists, and albums
routes — and two of them looked artwork up per track, so a 432-track artist
page cost 864 queries. This module batches artwork resolution into two IN
queries per request and gives every route the same response shape.
"""

import os

from sqlalchemy.orm import Session, selectinload

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


# --- The list projection --------------------------------------------------
#
# A full TrackResponse is ~570 bytes on the wire; a row in a list on the
# phone reads about a third of it. `fields=list` on the list routes returns
# only what a row draws, plays and edits from: identity, the three names, the
# genres (the edit sheet preloads them), the artwork paths, the duration
# (the lock-screen scrubber needs it) and the file extension (the cache
# names its files by it). The full shape stays the default, and stays on
# `/tracks/{id}`.

LIST_FIELDS = (
    "id",
    "title",
    "artist",
    "album",
    "genres",
    "artwork_path",
    "album_artwork_path",
    "artist_artwork_path",
    "duration_seconds",
    "file_ext",
)


def file_extension_of(file_path: str | None) -> str | None:
    extension = os.path.splitext(file_path or "")[1].lstrip(".").lower()
    return extension or None


def track_load_options(fields: str | None = None) -> list:
    """The relationships a payload needs loaded, and no more."""
    if fields == "list":
        return [selectinload(Track.track_genres)]
    return [selectinload(Track.track_artists), selectinload(Track.track_genres)]


def build_track_list_items(db: Session, tracks: list[Track]) -> list[dict]:
    if not tracks:
        return []

    album_map, artist_map = get_artwork_maps(db, tracks)
    items = []

    for track in tracks:
        album_artwork_path = album_map.get(normalize_album_key(track.album))
        items.append(
            {
                "id": track.id,
                "title": track.title,
                "artist": track.artist,
                "album": track.album,
                "genres": [item.genre for item in track.track_genres if item.genre],
                "artwork_path": album_artwork_path,
                "album_artwork_path": album_artwork_path,
                "artist_artwork_path": artist_map.get(normalize_artist_name(track.artist)),
                "duration_seconds": track.duration_seconds,
                "file_ext": file_extension_of(track.file_path),
            }
        )

    return items


def build_track_payloads(db: Session, tracks: list[Track], fields: str | None = None) -> list:
    """Full responses by default; the list projection on request."""
    if fields == "list":
        return build_track_list_items(db, tracks)
    return build_track_responses(db, tracks)


def payload_dict(payload) -> dict:
    """A payload as a plain dict, whichever shape it is."""
    return payload if isinstance(payload, dict) else payload.model_dump()
