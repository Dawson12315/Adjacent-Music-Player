from pathlib import Path
from typing import Optional

from mutagen import File as MutagenFile


def _first_value(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def parse_position(value) -> int | None:
    """"7", "7/12", "07" and the ID3 forms, to 7; anything else to None."""
    text = str(_first_value(value) or "").strip()
    if not text:
        return None
    head = text.split("/")[0].strip()
    digits = "".join(ch for ch in head if ch.isdigit())
    if not digits:
        return None
    number = int(digits)
    return number if 0 < number < 10000 else None


def extract_track_metadata(file_path: str) -> dict:
    path = Path(file_path)

    audio = MutagenFile(path)

    if audio is None:
        raise ValueError(f"Unsupported or unreadable audio file: {file_path}")

    tags = getattr(audio, "tags", {}) or {}

    title = _first_value(tags.get("TIT2")) or _first_value(tags.get("title"))
    artist = _first_value(tags.get("TPE1")) or _first_value(tags.get("artist"))
    album = _first_value(tags.get("TALB")) or _first_value(tags.get("album"))
    genre = _first_value(tags.get("TCON")) or _first_value(tags.get("genre"))
    track_number = parse_position(tags.get("TRCK")) or parse_position(tags.get("tracknumber"))
    disc_number = parse_position(tags.get("TPOS")) or parse_position(tags.get("discnumber"))

    if title is not None:
        title = str(title)
    if artist is not None:
        artist = str(artist)
    if album is not None:
        album = str(album)
    if genre is not None:
        genre = str(genre)

    if not title:
        title = path.stem

    return {
        "title": title,
        "artist": artist,
        "album": album,
        "genre": genre,
        "raw_title": title,
        "raw_artist": artist,
        "raw_album": album,
        "raw_genre": genre,
        "track_number": track_number,
        "disc_number": disc_number,
        "file_path": str(path),
        "duration_seconds": getattr(getattr(audio, "info", None), "length", None),
    }