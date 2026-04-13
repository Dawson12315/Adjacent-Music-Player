from pathlib import Path
from typing import Optional, Tuple


def extract_metadata_from_filename(file_path: str) -> Tuple[Optional[str], Optional[str], str]:
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