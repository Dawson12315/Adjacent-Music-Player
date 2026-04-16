import requests
from typing import Dict, Optional

LASTFM_BASE_URL = "http://ws.audioscrobbler.com/2.0/"


def _request_lastfm(params: dict) -> Dict:
    try:
        response = requests.get(
            LASTFM_BASE_URL,
            params=params,
            timeout=10,
        )
        data = response.json()
    except requests.RequestException as error:
        print(f"Last.fm lookup failed: {error}")
        return {"success": False, "tags": []}
    except ValueError:
        print("Last.fm lookup failed: response was not valid JSON")
        return {"success": False, "tags": []}

    if "error" in data:
        print(f"Last.fm API error {data.get('error')}: {data.get('message')}")
        return {"success": False, "tags": []}

    tags = data.get("toptags", {}).get("tag", [])
    return {
        "success": True,
        "tags": [tag.get("name") for tag in tags if tag.get("name")],
    }


def get_track_top_tags(
    mbid: Optional[str],
    api_key: str,
    track_name: Optional[str] = None,
    artist_name: Optional[str] = None,
) -> Dict:
    if not api_key:
        return {"success": False, "tags": []}

    if mbid:
        result = _request_lastfm(
            {
                "method": "track.getTopTags",
                "mbid": mbid,
                "api_key": api_key,
                "format": "json",
            }
        )
        if result["success"] and result["tags"]:
            return result
        if not result["success"]:
            return result

    if track_name and artist_name:
        result = _request_lastfm(
            {
                "method": "track.getTopTags",
                "track": track_name,
                "artist": artist_name,
                "autocorrect": 1,
                "api_key": api_key,
                "format": "json",
            }
        )
        return result

    return {"success": True, "tags": []}


def get_album_top_tags(
    album_name: Optional[str],
    artist_name: Optional[str],
    api_key: str,
) -> Dict:
    if not api_key or not album_name or not artist_name:
        return {"success": True, "tags": []}

    return _request_lastfm(
        {
            "method": "album.getTopTags",
            "album": album_name,
            "artist": artist_name,
            "autocorrect": 1,
            "api_key": api_key,
            "format": "json",
        }
    )


def get_artist_top_tags(
    artist_name: Optional[str],
    api_key: str,
) -> Dict:
    if not api_key or not artist_name:
        return {"success": True, "tags": []}

    return _request_lastfm(
        {
            "method": "artist.getTopTags",
            "artist": artist_name,
            "autocorrect": 1,
            "api_key": api_key,
            "format": "json",
        }
    )