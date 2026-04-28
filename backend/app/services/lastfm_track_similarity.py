import re
from typing import Dict, Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.track import Track
from app.models.track_lastfm_similarity import TrackLastfmSimilarity
from app.services.lastfm import get_similar_tracks
from app.utils.artist_normalization import normalize_artist_name


def build_track_key(artist: str, track: str) -> str:
    return f"{normalize_artist_name(artist)}::{normalize_artist_name(track)}"


def clean_lastfm_track_lookup_title(title: str) -> str:
    if not title:
        return ""

    cleaned = title.strip()

    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]*\]\s*", " ", cleaned)

    cleaned = re.sub(
        r"\s+-\s+(live|remaster(?:ed)?|radio edit|single version|album version|explicit|clean|instrumental|acoustic|demo|mono|stereo).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def ingest_similar_tracks_for_track(
    db: Session,
    track_id: int,
    limit: int = 25,
) -> Dict[str, Any]:
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        return {
            "success": False,
            "reason": "track_not_found",
            "track_id": track_id,
            "stored_count": 0,
            "tracks_returned": [],
        }

    if not track.title or not track.artist:
        return {
            "success": False,
            "reason": "missing_track_identity",
            "track_id": track_id,
            "stored_count": 0,
            "tracks_returned": [],
        }

    settings = db.query(AppSetting).first()
    api_key = settings.lastfm_api_key if settings else None

    if not api_key:
        return {
            "success": False,
            "reason": "missing_api_key",
            "track_id": track_id,
            "stored_count": 0,
            "tracks_returned": [],
        }

    lookup_title = clean_lastfm_track_lookup_title(track.title) or track.title
    source_key = build_track_key(track.artist, track.title)

    lastfm_result = get_similar_tracks(
        track_name=lookup_title,
        artist_name=track.artist,
        api_key=api_key,
        limit=limit,
    )

    if not lastfm_result["success"]:
        return {
            "success": False,
            "reason": lastfm_result.get("error", "lastfm_lookup_failed"),
            "track_id": track_id,
            "stored_count": 0,
            "tracks_returned": [],
            "lookup_title": lookup_title,
        }

    stored_count = 0
    stored_rows = []
    seen_similar_keys: set[str] = set()

    local_tracks = (
        db.query(Track)
        .filter(Track.artist.isnot(None), Track.title.isnot(None))
        .all()
    )

    local_track_lookup = {
        build_track_key(candidate.artist, candidate.title): candidate.id
        for candidate in local_tracks
        if candidate.artist and candidate.title
    }

    for item in lastfm_result["tracks"]:
        similar_track_name = item.get("name")
        similar_artist_name = item.get("artist")

        if not similar_track_name or not similar_artist_name:
            continue

        similar_key = build_track_key(similar_artist_name, similar_track_name)

        if similar_key == source_key:
            continue

        if similar_key in seen_similar_keys:
            continue

        seen_similar_keys.add(similar_key)

        matched_track_id = local_track_lookup.get(similar_key)

        existing_row = (
            db.query(TrackLastfmSimilarity)
            .filter(
                TrackLastfmSimilarity.source_track_id == track.id,
                TrackLastfmSimilarity.similar_track_key == similar_key,
            )
            .first()
        )

        if existing_row:
            existing_row.similar_track_name = similar_track_name
            existing_row.similar_artist_name = similar_artist_name
            existing_row.similar_track_id = matched_track_id
            existing_row.match_score = item.get("match_score")
            existing_row.similar_mbid = item.get("mbid")
        else:
            db.add(
                TrackLastfmSimilarity(
                    source_track_id=track.id,
                    similar_track_id=matched_track_id,
                    source_track_name=track.title,
                    source_artist_name=track.artist,
                    similar_track_name=similar_track_name,
                    similar_artist_name=similar_artist_name,
                    source_track_key=source_key,
                    similar_track_key=similar_key,
                    match_score=item.get("match_score"),
                    source_mbid=track.musicbrainz_recording_id,
                    similar_mbid=item.get("mbid"),
                )
            )

        stored_count += 1

        stored_rows.append(
            {
                "source_track_id": track.id,
                "similar_track_name": similar_track_name,
                "similar_artist_name": similar_artist_name,
                "similar_track_id": matched_track_id,
                "match_score": item.get("match_score"),
            }
        )

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        return {
            "success": False,
            "reason": "duplicate_similar_track_row",
            "track_id": track.id,
            "source_title": track.title,
            "lookup_title": lookup_title,
            "stored_count": 0,
            "tracks_returned": [],
            "error": str(error),
        }
    except Exception as error:
        db.rollback()
        return {
            "success": False,
            "reason": "similar_track_commit_failed",
            "track_id": track.id,
            "source_title": track.title,
            "lookup_title": lookup_title,
            "stored_count": 0,
            "tracks_returned": [],
            "error": str(error),
        }

    return {
        "success": True,
        "reason": "ok",
        "track_id": track.id,
        "source_title": track.title,
        "lookup_title": lookup_title,
        "stored_count": stored_count,
        "tracks_returned": stored_rows,
    }