from pathlib import Path
from typing import Optional

from mutagen import File as MutagenFile


def _first_value(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def extract_track_metadata(file_path: str) -> dict:
    path = Path(file_path)

    audio = MutagenFile(path)

    if audio is None:
        raise ValueError(f"Unsupported or unreadable audio file: {file_path}")

    tags = getattr(audio, "tags", {}) or {}

    title = _first_value(tags.get("TIT2")) or _first_value(tags.get("title"))
    artist = _first_value(tags.get("TPE1")) or _first_value(tags.get("artist"))
    album = _first_value(tags.get("TALB")) or _first_value(tags.get("album"))

    if title is not None:
        title = str(title)
    if artist is not None:
        artist = str(artist)
    if album is not None:
        album = str(album)

    if not title:
        title = path.stem

    return {
        "title": title,
        "artist": artist,
        "album": album,
        "file_path": str(path),
    }