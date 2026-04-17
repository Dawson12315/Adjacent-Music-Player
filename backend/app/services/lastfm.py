import hashlib
import requests
import time
from typing import Dict, Optional

LASTFM_BASE_URL = "http://ws.audioscrobbler.com/2.0/"


def build_lastfm_api_sig(params: dict, api_secret: str) -> str:
    filtered_params = {
        key: value
        for key, value in params.items()
        if value is not None and key not in {"format", "callback"}
    }

    signature_base = "".join(
        f"{key}{filtered_params[key]}"
        for key in sorted(filtered_params.keys())
    ) + api_secret

    return hashlib.md5(signature_base.encode("utf-8")).hexdigest()


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


def get_lastfm_session(
    token: str,
    api_key: str,
    api_secret: str,
) -> Dict:
    if not token or not api_key or not api_secret:
        return {
            "success": False,
            "session_key": None,
            "username": None,
            "error": "missing_credentials",
        }

    params = {
        "method": "auth.getSession",
        "api_key": api_key,
        "token": token,
        "format": "json",
    }

    api_sig = build_lastfm_api_sig(params, api_secret)

    try:
        response = requests.get(
            LASTFM_BASE_URL,
            params={
                **params,
                "api_sig": api_sig,
            },
            timeout=10,
        )
        data = response.json()
    except requests.RequestException as error:
        print(f"Last.fm session lookup failed: {error}")
        return {
            "success": False,
            "session_key": None,
            "username": None,
            "error": "request_failed",
        }
    except ValueError:
        print("Last.fm session lookup failed: response was not valid JSON")
        return {
            "success": False,
            "session_key": None,
            "username": None,
            "error": "invalid_json",
        }

    if "error" in data:
        print(f"Last.fm API error {data.get('error')}: {data.get('message')}")
        return {
            "success": False,
            "session_key": None,
            "username": None,
            "error": data.get("message", "api_error"),
        }

    session = data.get("session", {})

    return {
        "success": True,
        "session_key": session.get("key"),
        "username": session.get("name"),
        "error": None,
    }


def update_now_playing(
    api_key: str,
    api_secret: str,
    session_key: str,
    track_name: str,
    artist_name: str,
    album_name: Optional[str] = None,
    mbid: Optional[str] = None,
) -> Dict:
    if not api_key or not api_secret or not session_key:
        return {"success": False, "error": "missing_credentials"}

    params = {
        "method": "track.updateNowPlaying",
        "api_key": api_key,
        "sk": session_key,
        "artist": artist_name,
        "track": track_name,
        "format": "json",
    }

    if album_name:
        params["album"] = album_name

    if mbid:
        params["mbid"] = mbid

    api_sig = build_lastfm_api_sig(params, api_secret)

    try:
        response = requests.post(
            LASTFM_BASE_URL,
            data={
                **params,
                "api_sig": api_sig,
            },
            timeout=10,
        )
        data = response.json()
    except requests.RequestException as error:
        print(f"Last.fm now playing failed: {error}")
        return {"success": False, "error": "request_failed"}
    except ValueError:
        print("Last.fm now playing failed: invalid JSON")
        return {"success": False, "error": "invalid_json"}

    if "error" in data:
        print(f"Last.fm API error {data.get('error')}: {data.get('message')}")
        return {"success": False, "error": data.get("message", "api_error")}

    return {"success": True, "data": data}


def scrobble_track(
    api_key: str,
    api_secret: str,
    session_key: str,
    track_name: str,
    artist_name: str,
    album_name: Optional[str] = None,
    mbid: Optional[str] = None,
) -> Dict:
    if not api_key or not api_secret or not session_key:
        return {"success": False, "error": "missing_credentials"}

    timestamp = int(time.time())

    params = {
        "method": "track.scrobble",
        "api_key": api_key,
        "sk": session_key,
        "artist": artist_name,
        "track": track_name,
        "timestamp": timestamp,
        "format": "json",
    }

    if album_name:
        params["album"] = album_name

    if mbid:
        params["mbid"] = mbid

    api_sig = build_lastfm_api_sig(params, api_secret)

    try:
        response = requests.post(
            LASTFM_BASE_URL,
            data={
                **params,
                "api_sig": api_sig,
            },
            timeout=10,
        )
        data = response.json()
    except requests.RequestException as error:
        print(f"Last.fm scrobble failed: {error}")
        return {"success": False, "error": "request_failed"}
    except ValueError:
        print("Last.fm scrobble failed: invalid JSON")
        return {"success": False, "error": "invalid_json"}

    if "error" in data:
        print(f"Last.fm API error {data.get('error')}: {data.get('message')}")
        return {"success": False, "error": data.get("message", "api_error")}

    return {"success": True, "data": data}