from typing import Dict, Any

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
from app.utils.artist_normalization import normalize_artist_name
from app.services.lastfm import get_similar_artists


def ingest_similar_artists_for_artist(
    db: Session,
    artist_name: str,
    limit: int = 25,
) -> Dict[str, Any]:
    normalized_source_key = normalize_artist_name(artist_name)

    if not artist_name or not normalized_source_key:
        return {
            "success": False,
            "reason": "invalid_artist_name",
            "source_artist_name": artist_name,
            "source_artist_key": normalized_source_key,
            "stored_count": 0,
            "artists_returned": [],
        }

    settings = db.query(AppSetting).first()
    api_key = settings.lastfm_api_key if settings else None

    if not api_key:
        return {
            "success": False,
            "reason": "missing_api_key",
            "source_artist_name": artist_name,
            "source_artist_key": normalized_source_key,
            "stored_count": 0,
            "artists_returned": [],
        }

    lastfm_result = get_similar_artists(
        artist_name=artist_name,
        api_key=api_key,
        limit=limit,
    )

    if not lastfm_result["success"]:
        return {
            "success": False,
            "reason": lastfm_result.get("error", "lastfm_lookup_failed"),
            "source_artist_name": artist_name,
            "source_artist_key": normalized_source_key,
            "stored_count": 0,
            "artists_returned": [],
        }

    stored_count = 0
    stored_rows = []

    for item in lastfm_result["artists"]:
        similar_artist_name = item.get("name")
        similar_artist_key = normalize_artist_name(similar_artist_name)

        if not similar_artist_name or not similar_artist_key:
            continue

        if similar_artist_key == normalized_source_key:
            continue

        if normalized_source_key in similar_artist_key:
            continue

        existing_row = (
            db.query(ArtistLastfmSimilarity)
            .filter(
                ArtistLastfmSimilarity.source_artist_key == normalized_source_key,
                ArtistLastfmSimilarity.similar_artist_key == similar_artist_key,
            )
            .first()
        )

        if existing_row:
            existing_row.source_artist_name = artist_name
            existing_row.similar_artist_name = similar_artist_name
            existing_row.match_score = item.get("match_score")
            existing_row.source_mbid = existing_row.source_mbid or None
            existing_row.similar_mbid = item.get("mbid")
        else:
            db.add(
                ArtistLastfmSimilarity(
                    source_artist_name=artist_name,
                    source_artist_key=normalized_source_key,
                    similar_artist_name=similar_artist_name,
                    similar_artist_key=similar_artist_key,
                    match_score=item.get("match_score"),
                    source_mbid=None,
                    similar_mbid=item.get("mbid"),
                )
            )

        stored_count += 1
        stored_rows.append(
            {
                "source_artist_name": artist_name,
                "source_artist_key": normalized_source_key,
                "similar_artist_name": similar_artist_name,
                "similar_artist_key": similar_artist_key,
                "match_score": item.get("match_score"),
                "similar_mbid": item.get("mbid"),
            }
        )

    db.commit()

    return {
        "success": True,
        "reason": "ok",
        "source_artist_name": artist_name,
        "source_artist_key": normalized_source_key,
        "stored_count": stored_count,
        "artists_returned": stored_rows,
    }