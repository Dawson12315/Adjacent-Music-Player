import requests

from app.db import SessionLocal
from app.models.track import Track
from app.services.musicbrainz import _score_recording, USER_AGENT, MUSICBRAINZ_BASE_URL


TRACK_ID_TO_TEST = 1


def main():
    db = SessionLocal()

    try:
        track = db.query(Track).filter(Track.id == TRACK_ID_TO_TEST).first()

        if not track:
            print(f"Track {TRACK_ID_TO_TEST} not found.")
            return

        search_title = track.raw_title or track.title
        search_artist = track.raw_artist or track.artist

        print("=== LOCAL TRACK ===")
        print(f"id: {track.id}")
        print(f"title: {track.title}")
        print(f"raw_title: {track.raw_title}")
        print(f"artist: {track.artist}")
        print(f"raw_artist: {track.raw_artist}")
        print(f"stored_mbid: {track.musicbrainz_recording_id}")
        print()
        print("=== SEARCH INPUT ===")
        print(f"title: {search_title}")
        print(f"artist: {search_artist}")
        print()

        query = f'recording:"{search_title}" AND artist:"{search_artist}"'

        response = requests.get(
            f"{MUSICBRAINZ_BASE_URL}/recording",
            params={
                "query": query,
                "fmt": "json",
                "limit": 10,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        recordings = data.get("recordings", [])

        print(f"=== CANDIDATES ({len(recordings)}) ===")

        if not recordings:
            print("No candidates found.")
            return

        for index, recording in enumerate(recordings, start=1):
            artist_credit = " ".join(
                credit.get("name", "")
                for credit in recording.get("artist-credit", [])
                if isinstance(credit, dict)
            )

            score = _score_recording(recording, search_title, search_artist)

            print(f"\n#{index}")
            print(f"title: {recording.get('title')}")
            print(f"artist: {artist_credit}")
            print(f"id: {recording.get('id')}")
            print(f"score: {score}")

    finally:
        db.close()


if __name__ == "__main__":
    main()