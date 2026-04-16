from typing import Dict, List

from app.models.app_setting import AppSetting
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_genre import TrackGenre
from app.services.lastfm import (
    get_album_top_tags,
    get_artist_top_tags,
    get_track_top_tags,
)
from app.services.lastfm_genre_filter import clean_lastfm_genre_tags
from app.utils.artist_parsing import extract_featured_artists


def enrich_track_lastfm_tags(db, track_id: int) -> Dict:
    settings = db.query(AppSetting).first()
    api_key = settings.lastfm_api_key if settings else None

    if not api_key:
        return {
            "success": False,
            "reason": "missing_api_key",
            "track_id": track_id,
            "added_genres": [],
        }

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        return {
            "success": False,
            "reason": "track_not_found",
            "track_id": track_id,
            "added_genres": [],
        }

    if not track.musicbrainz_recording_id:
        return {
            "success": False,
            "reason": "missing_musicbrainz_recording_id",
            "track_id": track_id,
            "added_genres": [],
        }

    artist_names: List[str] = []

    if track.artist:
        artist_names.append(track.artist)

    if track.raw_artist:
        artist_names.append(track.raw_artist)

    artist_names.extend(
        row.artist_name
        for row in db.query(TrackArtist).filter(TrackArtist.track_id == track.id).all()
    )

    artist_names.extend(extract_featured_artists(track.raw_title or ""))
    artist_names.extend(extract_featured_artists(track.raw_album or ""))

    artist_names = [name.strip() for name in artist_names if name]

    lastfm_result = get_track_top_tags(
        track.musicbrainz_recording_id,
        api_key,
        track_name=track.title,
        artist_name=track.artist,
    )
    lastfm_source = "track"

    if not lastfm_result["success"]:
        return {
            "success": False,
            "reason": "lastfm_lookup_failed",
            "track_id": track.id,
            "added_genres": [],
        }

    raw_tags = lastfm_result["tags"]

    if not raw_tags:
        album_result = get_album_top_tags(
            track.album,
            track.artist,
            api_key,
        )

        if not album_result["success"]:
            return {
                "success": False,
                "reason": "lastfm_lookup_failed",
                "track_id": track.id,
                "added_genres": [],
            }

        if album_result["tags"]:
            raw_tags = album_result["tags"]
            lastfm_source = "album"

    if not raw_tags:
        artist_result = get_artist_top_tags(
            track.artist,
            api_key,
        )

        if not artist_result["success"]:
            return {
                "success": False,
                "reason": "lastfm_lookup_failed",
                "track_id": track.id,
                "added_genres": [],
            }

        raw_tags = artist_result["tags"]
        if raw_tags:
            lastfm_source = "artist"

    cleaned_tags = clean_lastfm_genre_tags(
        raw_tags,
        artist_names=artist_names,
        track_title=track.title,
        album_title=track.album,
    )

    existing_rows = db.query(TrackGenre).filter(TrackGenre.track_id == track.id).all()
    existing_keys = {row.genre.casefold() for row in existing_rows if row.genre}

    added_genres: List[str] = []

    for genre_name in cleaned_tags:
        if genre_name.casefold() in existing_keys:
            continue

        db.add(
            TrackGenre(
                track_id=track.id,
                genre=genre_name,
            )
        )
        existing_keys.add(genre_name.casefold())
        added_genres.append(genre_name)

    track.lastfm_tags_enriched = True

    db.commit()

    return {
        "success": True,
        "reason": "ok",
        "track_id": track.id,
        "raw_tags": raw_tags,
        "cleaned_tags": cleaned_tags,
        "added_genres": added_genres,
        "lastfm_source": lastfm_source
    }