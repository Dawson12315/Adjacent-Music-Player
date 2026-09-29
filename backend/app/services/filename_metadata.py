from pathlib import Path
from typing import Optional, Tuple


def extract_metadata_from_filename(file_path: str) -> Tuple[Optional[str], Optional[str], str]:
    """(artist, album, title) from "Artist - Album - 01 - Title" or "Artist - Title"."""
    filename = Path(file_path).stem
    parts = [part.strip() for part in filename.split(" - ")]

    if len(parts) >= 4:
        artist = parts[0]
        album = parts[1]
        title = parts[-1]
        return artist, album, title

    if len(parts) >= 2:
        artist = parts[0]
        title = parts[-1]
        return artist, None, title

    return None, None, filename


def extract_track_number_from_filename(file_path: str) -> Optional[int]:
    """The track's number when the name carries one, else None.

    "Artist - Album - 01 - Title": the part before the title. "01 Title" and
    "01. Title" (a bare numbered file inside an album folder) count too. A
    four-digit run is a year, not a position.
    """
    filename = Path(file_path).stem
    parts = [part.strip() for part in filename.split(" - ")]

    candidate = None
    if len(parts) >= 3:
        candidate = parts[-2]
    elif len(parts) == 1:
        head = filename.split(" ", 1)[0].rstrip(".")
        candidate = head

    if not candidate or not candidate.isdigit() or len(candidate) > 3:
        return None

    number = int(candidate)
    return number if number > 0 else None
