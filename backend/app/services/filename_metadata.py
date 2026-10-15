"""What a file's name and its folders say about a track.

Used where the tags are silent. The names people actually use:

    Artist - Album - 01 - Title.flac       (the library's own convention)
    Artist - 01 - Title.flac
    Artist - Title.flac
    01 - Title.flac                         (a soundtrack rip in its album folder)
    01 Title.flac, 01. Title.flac, 1-07 Title.flac
    Title.flac

The number is found by what it is, not by where it sits: "07 - Southern
Messiah" is track seven, not a song by an artist called "07". Then the
folders: Artist/Album (Year)/[Disc 2]/file is the layout nearly every
library follows, and it is where an untagged soundtrack's artist lives.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

# A track number as a name part: "7", "07", "007", "1-07" (disc-track),
# "2.07", optionally with a trailing dot. Four digits is a year.
_NUMBER_PART = re.compile(r"^(?:(\d{1,2})[-.])?(\d{1,3})\.?$")

# A bare numbered file: "01 Title", "01. Title", "01 - Title", "01_Title",
# "1-07 Title", "01) Title". The separator decides whether the digits are a
# position: "7 Rings" and "22" keep their names.
_NUMBERED_STEM = re.compile(
    r"^(?:(\d{1,2})[-.])?(\d{1,3})(?P<sep>\.\s*|\)\s*|[-_]+\s*|\s+-\s+|\s+)(?P<title>\S.*)$"
)

# Folders that sit between an album and its files.
_DISC_FOLDER = re.compile(
    r"^(?:(?:disc|disk|cd|dvd|side|vol\.?|volume|part)\s*[-_ ]?\s*(?:\d+|[a-z])?"
    r"|\d{1,2}\s*(?:vinyl|cd|disc|disk)\s*\d*)$",
    flags=re.IGNORECASE,
)

# Folder names nothing should be named after.
_GENERIC_FOLDERS = {
    "music", "media", "audio", "library", "songs", "albums", "artists",
    "downloads", "download", "flac", "mp3", "lossless", "volumes", "mnt",
    "srv", "data", "home", "users", "shares", "share", "nas", "various",
    "various artists", "compilations", "soundtracks", "ost", "unknown",
}

_YEAR_SUFFIX = re.compile(r"\s*[\(\[]\s*(?:19|20)\d{2}\s*[\)\]]\s*$")
_FORMAT_SUFFIX = re.compile(
    r"\s*[\(\[]\s*(?:flac|mp3|aac|alac|m4a|ogg|opus|wav|web|cd|vinyl|lossless|hi-?res"
    r"|\d{2,4}\s*(?:kbps|k|bit)|\d+\s*bit|16-?bit|24-?bit|\d+(?:\.\d+)?\s*khz)[^\)\]]*[\)\]]\s*$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class FilenameParts:
    artist: Optional[str]
    album: Optional[str]
    title: Optional[str]
    track_number: Optional[int]
    disc_number: Optional[int]


def _as_number(text: str) -> Optional[int]:
    number = int(text)
    return number if number > 0 else None


def parse_filename(file_path: str) -> FilenameParts:
    """Everything the file's own name says. Fields it does not carry are
    None; a title is always found (the whole stem, if nothing else)."""
    stem = Path(file_path).stem.strip()
    parts = [part.strip() for part in stem.split(" - ")]
    parts = [part for part in parts if part]

    if len(parts) >= 2:
        for index, part in enumerate(parts):
            match = _NUMBER_PART.match(part)
            if not match:
                continue
            disc_text, number_text = match.groups()
            # A leading three-digit act ("112 - Cupid") is a name, not a
            # position, unless it is zero-padded.
            if index == 0 and len(number_text) == 3 and not number_text.startswith("0"):
                continue
            before = parts[:index]
            after = parts[index + 1:]
            if not after:
                # "Artist - Title - 07": the number is part of the title.
                continue
            artist = before[0] if before else None
            album = " - ".join(before[1:]) if len(before) >= 2 else None
            return FilenameParts(
                artist=artist,
                album=album,
                title=" - ".join(after),
                track_number=_as_number(number_text),
                disc_number=_as_number(disc_text) if disc_text else None,
            )

    if len(parts) >= 4:
        return FilenameParts(parts[0], parts[1], parts[-1], None, None)

    if len(parts) >= 2:
        return FilenameParts(parts[0], None, parts[-1], None, None)

    numbered = _NUMBERED_STEM.match(stem)
    if numbered:
        disc_text, number_text, separator, title = numbered.group(1, 2, "sep", "title")
        # Only a position that reads as one: zero-padded, or followed by a
        # separator that is not just a space ("7 Rings" is a song).
        padded = number_text.startswith("0") and len(number_text) >= 2
        separated = not separator.isspace()
        return FilenameParts(
            artist=None,
            album=None,
            title=title.strip() if (padded or separated) else stem,
            track_number=_as_number(number_text) if len(number_text) <= 3 else None,
            disc_number=_as_number(disc_text) if disc_text else None,
        )

    return FilenameParts(None, None, stem or None, None, None)


def extract_metadata_from_filename(file_path: str) -> Tuple[Optional[str], Optional[str], str]:
    """(artist, album, title) from the file's name; kept for the scripts
    and tests that read it this way."""
    parsed = parse_filename(file_path)
    return parsed.artist, parsed.album, parsed.title or Path(file_path).stem


def extract_track_number_from_filename(file_path: str) -> Optional[int]:
    """The track's number when the name carries one, else None."""
    return parse_filename(file_path).track_number


def clean_folder_name(name: str) -> str:
    """An album folder's name without its year and format decorations:
    "Dune - Part Two (2024) [FLAC]" -> "Dune - Part Two"."""
    cleaned = name.strip()
    for _ in range(3):
        before = cleaned
        cleaned = _FORMAT_SUFFIX.sub("", cleaned)
        cleaned = _YEAR_SUFFIX.sub("", cleaned)
        cleaned = cleaned.strip()
        if cleaned == before:
            break
    return cleaned or name.strip()


def is_disc_folder(name: str) -> bool:
    return bool(_DISC_FOLDER.match(name.strip()))


def extract_metadata_from_folders(
    file_path: str, base_path: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """(artist, album) from the folders a file sits in.

    The nearest folder that is not a disc folder is the album; its parent
    is the artist. Neither may be the library root itself (or anything
    above it), and a folder with a generic name ("Music", "Lossless")
    names nothing. The album folder's "Artist - " prefix, if it repeats
    the artist, is dropped.
    """
    path = Path(file_path)
    folders = list(path.parents)[:-1]  # nearest first, root excluded

    if base_path:
        try:
            base = Path(base_path).resolve()
            depth = len(path.resolve().relative_to(base).parts) - 1
        except (ValueError, OSError):
            depth = len(folders)
        folders = folders[:depth]

    names = [folder.name for folder in folders if folder.name]
    album_folder = None
    artist_folder = None
    for index, name in enumerate(names):
        if is_disc_folder(name):
            continue
        album_folder = name
        if index + 1 < len(names):
            artist_folder = names[index + 1]
        break

    artist = None
    if artist_folder and artist_folder.strip().lower() not in _GENERIC_FOLDERS:
        artist = artist_folder.strip()

    album = None
    if album_folder:
        album = clean_folder_name(album_folder)
        if album.lower() in _GENERIC_FOLDERS:
            album = None
        elif artist and album.lower().startswith(artist.lower() + " - "):
            album = album[len(artist) + 3:].strip() or album

    return artist, album
