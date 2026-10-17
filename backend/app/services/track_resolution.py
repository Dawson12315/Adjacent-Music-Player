"""From a file's tags, name and folders to the fields a track row holds.

One function, used by the scanner for new files, for re-reads of edited
files, and by the repair scripts, so every path through the system agrees on
what a track is called.

The order of trust is the same for every field: the tag, then the file's
name, then its folders. A tag that is present wins outright; the name and
the folders only ever fill what the tag left out.
"""

from pathlib import Path
from typing import Optional

from app.services.filename_metadata import (
    extract_metadata_from_folders,
    parse_filename,
)
from app.services.genre_normalizer import normalize_genre
from app.services.metadata_normalizer import (
    normalize_album,
    normalize_artist_list,
    normalize_genre_list,
    normalize_primary_artist,
    normalize_title,
)


def _text(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_track_fields(metadata: dict, file_path: str, base_path: Optional[str] = None) -> dict:
    """The row's fields for a file, given what its tags said.

    `metadata` is what `extract_track_metadata` returned (or a subset of
    it). Returns title, artist, album, genre, the credited `artists`, the
    `genres` list, the raw tag values, the positions, and `sources`: which
    of tag / filename / folder each named field came from, for the log.
    """
    stem = Path(file_path).stem
    name = parse_filename(file_path)

    raw_title = _text(metadata.get("title"))
    raw_artist = _text(metadata.get("artist"))
    raw_album_artist = _text(metadata.get("album_artist"))
    raw_album = _text(metadata.get("album"))
    raw_genre = _text(metadata.get("raw_genre")) or _text(metadata.get("genre"))

    sources: dict[str, str] = {}

    # A title tag that merely repeats the filename ("07 - Southern Messiah")
    # is no title at all; the name parser knows what to do with it.
    tagged_title = raw_title if raw_title and raw_title != stem.strip() else None
    # "Artist - Title" (or "Artist & Guest - Title") in the title tag is a
    # filename pasted by the tagger: the part after the dash is the title.
    if tagged_title and " - " in tagged_title:
        for prefix in (raw_artist, raw_album_artist):
            if prefix and tagged_title.lower().startswith(prefix.lower()):
                head, _, tail = tagged_title.partition(" - ")
                if tail.strip():
                    tagged_title = tail.strip()
                break
    if tagged_title:
        title_source, title_value = "tag", tagged_title
    else:
        title_source, title_value = "filename", (name.title or stem)
    title = normalize_title(title_value) or normalize_title(name.title or "") or stem
    sources["title"] = title_source

    folder_artist = folder_album = None
    needs_folders = not (raw_artist or raw_album_artist or name.artist) or not (raw_album or name.album)
    if needs_folders:
        folder_artist, folder_album = extract_metadata_from_folders(file_path, base_path)

    if raw_artist:
        artist_source, artist_value = "tag", raw_artist
    elif raw_album_artist:
        artist_source, artist_value = "album artist tag", raw_album_artist
    elif name.artist:
        artist_source, artist_value = "filename", name.artist
    elif folder_artist:
        artist_source, artist_value = "folder", folder_artist
    else:
        artist_source, artist_value = "none", None
    sources["artist"] = artist_source

    if raw_album:
        album_source, album_value = "tag", raw_album
    elif name.album:
        album_source, album_value = "filename", name.album
    elif folder_album:
        album_source, album_value = "folder", folder_album
    else:
        album_source, album_value = "none", None
    sources["album"] = album_source

    artists = normalize_artist_list(artist_value)
    artist = artists[0] if artists else None
    album = normalize_album(album_value)
    # The record's artist, only when the file says so. None here means the
    # album groups on the track artist, which is right for a normal album
    # and for a soundtrack filed under its composer's folder.
    album_artist = normalize_primary_artist(raw_album_artist) if raw_album_artist else None

    genres = normalize_genre_list(metadata.get("genre"))
    genre = genres[0] if genres else normalize_genre(metadata.get("genre"))

    track_number = metadata.get("track_number")
    track_number = int(track_number) if track_number else (name.track_number or 0)
    disc_number = metadata.get("disc_number") or name.disc_number

    return {
        "title": title,
        "artist": artist,
        "album": album,
        "genre": genre,
        "artists": artists,
        "genres": genres,
        "raw_title": raw_title,
        "raw_artist": raw_artist,
        "raw_album": raw_album,
        "raw_genre": raw_genre,
        "album_artist": album_artist,
        "raw_album_artist": raw_album_artist,
        "track_number": track_number,
        "disc_number": disc_number,
        "sources": sources,
    }
