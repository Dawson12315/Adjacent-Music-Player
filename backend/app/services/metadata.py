"""Reading tags from an audio file.

One reader for every container: mutagen's "easy" interface maps ID3 frames,
MP4 atoms and Vorbis comments onto the same key names, so an .m4a is read
exactly like a .flac. (It was not: the reader asked for TIT2/title only, which
MP4 files do not have, so every .m4a was imported untagged and lived on its
filename alone.)

A tag that is missing is reported as None, never as the filename: the scanner
owns the fallbacks and needs to know which fields the file actually carries.
"""

from pathlib import Path

from mutagen import File as MutagenFile

# Keys tried in order: the easy name, then the raw ID3 frame for the formats
# mutagen has no easy wrapper for (WAV and AIFF keep ID3 frames by name).
_TITLE_KEYS = ("title", "TIT2")
_ARTIST_KEYS = ("artist", "TPE1")
_ALBUM_ARTIST_KEYS = ("albumartist", "TPE2", "aART")
_ALBUM_KEYS = ("album", "TALB")
_GENRE_KEYS = ("genre", "TCON")
_TRACK_KEYS = ("tracknumber", "TRCK")
_DISC_KEYS = ("discnumber", "TPOS")

# What separates the values of a multi-valued tag when they are joined into
# one string. The artist splitter treats ";" as a hard separator.
MULTI_VALUE_JOINER = "; "


def _clean_text(value) -> str:
    """One tag value as text: NULs and surrounding whitespace gone."""
    text = str(value).replace("\x00", " ")
    return " ".join(text.split())


def _values(tags, keys) -> list[str]:
    """Every value of the first key the tags carry, as clean text.

    An ID3 frame holds its values in `.text` (a genre frame in `.genres`,
    which also turns the numeric "(17)" form into a name); Vorbis and easy
    tags hold a list. A frame that was simply str()'d gave its values
    NUL-joined, which is how "Rock\\x00Pop" reached the genre column.
    """
    for key in keys:
        try:
            raw = tags.get(key)
        except (KeyError, ValueError):
            raw = None
        if raw is None:
            continue
        if hasattr(raw, "genres"):
            items = list(raw.genres)
        elif hasattr(raw, "text"):
            items = list(raw.text)
        elif isinstance(raw, (list, tuple)):
            items = list(raw)
        else:
            items = [raw]
        cleaned = [text for text in (_clean_text(item) for item in items) if text]
        if cleaned:
            return cleaned
    return []


def _first(tags, keys) -> str | None:
    values = _values(tags, keys)
    return values[0] if values else None


def _joined(tags, keys) -> str | None:
    """Multi-valued credits ("Kodak Black", "1900Rugrat") as one field the
    normaliser can split again; a single value comes back untouched."""
    values = _values(tags, keys)
    if not values:
        return None
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return MULTI_VALUE_JOINER.join(unique)


def _first_value(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def parse_position(value) -> int | None:
    """"7", "7/12", "07" and the ID3 forms, to 7; anything else to None."""
    if hasattr(value, "text"):
        value = list(value.text)
    text = str(_first_value(value) or "").strip()
    if not text:
        return None
    head = text.split("/")[0].strip()
    digits = "".join(ch for ch in head if ch.isdigit())
    if not digits:
        return None
    number = int(digits)
    return number if 0 < number < 10000 else None


def _position(tags, keys) -> int | None:
    for key in keys:
        try:
            raw = tags.get(key)
        except (KeyError, ValueError):
            raw = None
        if raw is None:
            continue
        number = parse_position(raw)
        if number:
            return number
    return None


def extract_track_metadata(file_path: str) -> dict:
    """The file's tags, with None for anything it does not carry.

    `title`, `artist`, `album`, `genre` and `album_artist` are the tag values
    (multi-valued artist and genre tags joined with "; "). The `raw_*` keys
    repeat them for callers that store what the file said. `title` is None
    when the file has no title tag — it used to be the filename, which hid
    the difference between a tagged title and no title at all.
    """
    path = Path(file_path)

    audio = MutagenFile(path, easy=True)

    if audio is None:
        raise ValueError(f"Unsupported or unreadable audio file: {file_path}")

    tags = getattr(audio, "tags", None) or {}

    title = _first(tags, _TITLE_KEYS)
    artist = _joined(tags, _ARTIST_KEYS)
    album_artist = _joined(tags, _ALBUM_ARTIST_KEYS)
    album = _first(tags, _ALBUM_KEYS)
    genre = _joined(tags, _GENRE_KEYS)
    track_number = _position(tags, _TRACK_KEYS)
    disc_number = _position(tags, _DISC_KEYS)

    return {
        "title": title,
        "artist": artist,
        "album_artist": album_artist,
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
