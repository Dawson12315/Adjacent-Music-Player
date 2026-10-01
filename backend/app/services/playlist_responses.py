"""One place that turns Playlist rows into PlaylistResponse payloads.

A playlist row on a client shows more than its name: how many tracks it
holds, and a mosaic of its first few albums when it has no cover of its own.
Both come from here in two queries for the whole listing, however many
playlists a user has, rather than a query per playlist.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.playlist import Playlist
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.schemas.playlist import PlaylistPreviewItem, PlaylistResponse
from app.services.track_responses import (
    album_artwork_key,
    get_artwork_maps,
    resolve_album_artwork,
)

# A mosaic is four tiles: the first four distinct albums, in playlist order.
PREVIEW_TILES = 4
# How far into each playlist the preview looks for those albums. A playlist
# that opens with twelve tracks from one album gets a single-cover preview,
# which is what it looks like anyway.
_PREVIEW_SCAN_ROWS = 12
# Stays under SQLite's bound-parameter ceiling.
_IN_CHUNK_SIZE = 500


def _track_counts(db: Session, playlist_ids: list[int]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for start in range(0, len(playlist_ids), _IN_CHUNK_SIZE):
        chunk = playlist_ids[start : start + _IN_CHUNK_SIZE]
        for playlist_id, count in (
            db.query(PlaylistTrack.playlist_id, func.count(PlaylistTrack.id))
            .filter(PlaylistTrack.playlist_id.in_(chunk))
            .group_by(PlaylistTrack.playlist_id)
            .all()
        ):
            counts[playlist_id] = int(count)
    return counts


def _previews(db: Session, playlist_ids: list[int]) -> dict[int, list[PlaylistPreviewItem]]:
    rows: list[tuple[int, Track]] = []
    for start in range(0, len(playlist_ids), _IN_CHUNK_SIZE):
        chunk = playlist_ids[start : start + _IN_CHUNK_SIZE]
        ranked = (
            db.query(
                PlaylistTrack.playlist_id.label("playlist_id"),
                PlaylistTrack.track_id.label("track_id"),
                func.row_number()
                .over(
                    partition_by=PlaylistTrack.playlist_id,
                    order_by=(PlaylistTrack.position.asc(), PlaylistTrack.id.asc()),
                )
                .label("rank"),
            )
            .filter(PlaylistTrack.playlist_id.in_(chunk))
            .subquery()
        )
        rows.extend(
            (playlist_id, track)
            for playlist_id, track in (
                db.query(ranked.c.playlist_id, Track)
                .join(Track, Track.id == ranked.c.track_id)
                .filter(ranked.c.rank <= _PREVIEW_SCAN_ROWS)
                .order_by(ranked.c.playlist_id.asc(), ranked.c.rank.asc())
                .all()
            )
        )

    if not rows:
        return {}

    album_map, _artist_map = get_artwork_maps(db, [track for _, track in rows])
    previews: dict[int, list[PlaylistPreviewItem]] = {}
    seen: dict[int, set[str]] = {}
    for playlist_id, track in rows:
        items = previews.setdefault(playlist_id, [])
        if len(items) >= PREVIEW_TILES:
            continue
        album_key = album_artwork_key(track.album, track.artist)
        key = album_key or f"track:{track.id}"
        keys = seen.setdefault(playlist_id, set())
        if key in keys:
            continue
        keys.add(key)
        items.append(
            PlaylistPreviewItem(
                title=track.title,
                album=track.album,
                artwork_path=resolve_album_artwork(album_map, track.album, track.artist),
            )
        )
    return previews


def build_playlist_responses(db: Session, playlists: list[Playlist]) -> list[PlaylistResponse]:
    if not playlists:
        return []

    playlist_ids = [playlist.id for playlist in playlists]
    counts = _track_counts(db, playlist_ids)
    previews = _previews(db, playlist_ids)

    return [
        PlaylistResponse(
            id=playlist.id,
            name=playlist.name,
            is_system=bool(playlist.is_system),
            system_key=playlist.system_key,
            artwork_path=playlist.artwork_path,
            track_count=counts.get(playlist.id, 0),
            preview=previews.get(playlist.id, []),
        )
        for playlist in playlists
    ]


def build_playlist_response(db: Session, playlist: Playlist) -> PlaylistResponse:
    return build_playlist_responses(db, [playlist])[0]
