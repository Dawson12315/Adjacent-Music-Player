import os
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv


ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH)

EMAIL = os.getenv("MUSICBRAINZ_EMAIL", "unknown@example.com")

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"
USER_AGENT = f"Adjacent/1.0 ({EMAIL})"

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
})


def _normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(value.lower().split()).strip()


def _title_flags(title: str) -> set[str]:
    flags = set()
    lowered = _normalize(title)

    for keyword in ["instrumental", "remix", "live", "acoustic", "edit"]:
        if keyword in lowered:
            flags.add(keyword)

    return flags


def _score_recording(recording: dict, title: str, artist: str) -> int:
    score = 0

    wanted_title = _normalize(title)
    wanted_artist = _normalize(artist)

    recording_title = _normalize(recording.get("title"))
    artist_credit = " ".join(
        credit.get("name", "")
        for credit in recording.get("artist-credit", [])
        if isinstance(credit, dict)
    )
    recording_artist = _normalize(artist_credit)

    if recording_title == wanted_title:
        score += 100
    elif wanted_title and wanted_title in recording_title:
        score += 50

    if recording_artist == wanted_artist:
        score += 100
    elif wanted_artist and wanted_artist in recording_artist:
        score += 50

    wanted_flags = _title_flags(title)
    recording_flags = _title_flags(recording.get("title", ""))

    for flag in wanted_flags:
        if flag in recording_flags:
            score += 25

    if wanted_flags != recording_flags:
        score -= 10 * len(wanted_flags.symmetric_difference(recording_flags))

    return score


def _search_recordings(query: str) -> list[dict]:
    attempts = 2

    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                f"{MUSICBRAINZ_BASE_URL}/recording",
                params={
                    "query": query,
                    "fmt": "json",
                    "limit": 5,
                },
                timeout=15,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("recordings", [])

        except requests.RequestException as error:
            print(f"MusicBrainz lookup failed (attempt {attempt}/{attempts}): {error}")

            if attempt < attempts:
                time.sleep(1.5 * attempt)

    return []


def find_recording_mbid(
    title: Optional[str],
    artist: Optional[str],
    raw_title: Optional[str] = None,
    raw_artist: Optional[str] = None,
) -> Optional[str]:
    normalized_title = title or ""
    normalized_artist = artist or ""
    raw_title_value = raw_title or normalized_title
    raw_artist_value = raw_artist or normalized_artist

    if not normalized_title or not normalized_artist:
        return None

    raw_query = f'recording:"{raw_title_value}" AND artist:"{raw_artist_value}"'
    normalized_query = f'recording:"{normalized_title}" AND artist:"{normalized_artist}"'
    loose_query = f"{normalized_title} {normalized_artist}"

    search_attempts = []

    search_attempts.append(
        {
            "query": raw_query,
            "score_title": raw_title_value,
            "score_artist": raw_artist_value,
        }
    )

    if _normalize(raw_query) != _normalize(normalized_query):
        search_attempts.append(
            {
                "query": normalized_query,
                "score_title": normalized_title,
                "score_artist": normalized_artist,
            }
        )

    if _normalize(loose_query) not in {
        _normalize(raw_query),
        _normalize(normalized_query),
    }:
        search_attempts.append(
            {
                "query": loose_query,
                "score_title": normalized_title,
                "score_artist": normalized_artist,
            }
        )

    for attempt in search_attempts:
        recordings = _search_recordings(attempt["query"])

        if not recordings:
            continue

        best_recording = max(
            recordings,
            key=lambda recording: _score_recording(
                recording,
                attempt["score_title"],
                attempt["score_artist"],
            ),
        )

        return best_recording.get("id")

    return None