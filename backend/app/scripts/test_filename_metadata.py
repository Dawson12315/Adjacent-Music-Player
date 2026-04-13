from app.services.filename_metadata import extract_metadata_from_filename


EXAMPLES = [
    "/Volumes/media/music/Britney Spears/Me Against the Music (2003)/12 Vinyl 01/Britney Spears - Me Against the Music - 01 - Me Against the Music (Peter Rauhofer's Electrohouse remix).flac",
    "/Volumes/media/music/Kid Rock/Early Mornin' Stoned Pimp (1996)/Kid Rock - Early Mornin' Stoned Pimp - 16 - Outro.mp3",
    "/Volumes/media/music/Random Folder/Some Artist - Some Song.mp3",
    "/Volumes/media/music/Loose Track.mp3",
]


def main():
    for file_path in EXAMPLES:
        artist, album, title = extract_metadata_from_filename(file_path)
        print(file_path)
        print(f"  artist: {artist}")
        print(f"  album: {album}")
        print(f"  title: {title}")
        print()


if __name__ == "__main__":
    main()