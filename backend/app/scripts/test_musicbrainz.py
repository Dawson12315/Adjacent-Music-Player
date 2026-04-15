from app.services.musicbrainz import find_recording_mbid


def run_tests():
    print("=== MusicBrainz Test ===\n")

    tests = [
        ("Break Free", "Ariana Grande"),
        ("7 rings", "Ariana Grande"),
        ("Nonexistent Track Example", "Fake Artist"),
    ]

    for title, artist in tests:
        print(f"Searching: {title} — {artist}")
        mbid = find_recording_mbid(title, artist)
        print(f"Result: {mbid}\n")


if __name__ == "__main__":
    run_tests()