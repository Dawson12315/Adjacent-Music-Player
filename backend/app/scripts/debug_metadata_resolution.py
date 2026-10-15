"""Show how one file would be imported: its tags, its name, and the result."""

import sys

from app.config import settings
from app.services.filename_metadata import extract_metadata_from_folders, parse_filename
from app.services.metadata import extract_track_metadata
from app.services.track_resolution import resolve_track_fields

FILE_PATH = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/media/music/Kid Rock/Early Mornin' Stoned Pimp (1996)/Kid Rock - Early Mornin' Stoned Pimp - 16 - Outro.mp3"


def main():
    embedded = extract_track_metadata(FILE_PATH)
    print("Tags:")
    for key in ("title", "artist", "album_artist", "album", "genre", "track_number", "disc_number"):
        print(f"  {key}: {embedded.get(key)!r}")

    print("Name:", parse_filename(FILE_PATH))
    print("Folders:", extract_metadata_from_folders(FILE_PATH, settings.music_library_path))

    fields = resolve_track_fields(embedded, FILE_PATH, settings.music_library_path)
    print("Result:")
    for key in ("title", "artist", "album", "artists", "genre", "genres", "track_number", "disc_number", "sources"):
        print(f"  {key}: {fields[key]!r}")


if __name__ == "__main__":
    main()
