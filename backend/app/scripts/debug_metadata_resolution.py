from app.services.filename_metadata import extract_metadata_from_filename
from app.services.metadata import extract_track_metadata
from app.services.metadata_normalizer import (
    normalize_album,
    normalize_artist,
    normalize_title,
)


FILE_PATH = "/Volumes/media/music/Britney Spears/Me Against the Music (2003)/12 Vinyl 01/Britney Spears - Me Against the Music - 01 - Me Against the Music (Peter Rauhofer's Electrohouse remix).flac"


def main():
    embedded = extract_track_metadata(FILE_PATH)
    filename_artist, filename_album, filename_title = extract_metadata_from_filename(FILE_PATH)

    raw_title = embedded.get("title")
    raw_artist = embedded.get("artist")
    raw_album = embedded.get("album")

    use_filename_title = False
    
    if not raw_title:
        use_filename_title = True
    elif " - " in raw_title and filename_title:
        use_filename_title = True
    
    final_title = normalize_title(
        filename_title if use_filename_title else raw_title
    )
    final_artist = normalize_artist(raw_artist or filename_artist)
    final_album = normalize_album(raw_album or filename_album)

    print("EMBEDDED")
    print(f"  raw_title:  {raw_title!r}")
    print(f"  raw_artist: {raw_artist!r}")
    print(f"  raw_album:  {raw_album!r}")
    print()

    print("FILENAME")
    print(f"  artist: {filename_artist!r}")
    print(f"  album:  {filename_album!r}")
    print(f"  title:  {filename_title!r}")
    print()

    print("FINAL")
    print(f"  title:  {final_title!r}")
    print(f"  artist: {final_artist!r}")
    print(f"  album:  {final_album!r}")


if __name__ == "__main__":
    main()