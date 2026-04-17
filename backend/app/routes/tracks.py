from pathlib import Path
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_genre import TrackGenre
from app.schemas.track import TrackResponse
from app.schemas.track_edit import TrackUpdate

from app.models.playlist_track import PlaylistTrack
from app.models.playback_queue_item import PlaybackQueueItem
from app.models.playback_session import PlaybackSession

from app.services.metadata_normalizer import normalize_genre_list
from app.services.musicbrainz import find_recording_mbid

from app.models.app_setting import AppSetting
from app.services.lastfm import scrobble_track, update_now_playing

router = APIRouter()


@router.get("/tracks/count", tags=["tracks"])
def get_track_count(db: Session = Depends(get_db)):
    count = db.query(func.count(Track.id)).scalar()
    return {"count": count}


@router.get("/tracks", response_model=list[TrackResponse], tags=["tracks"])
def list_tracks(db: Session = Depends(get_db)):
    tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .order_by(Track.artist.asc(), Track.album.asc(), Track.title.asc())
        .all()
    )

    response = []

    for track in tracks:
        response.append(
            TrackResponse(
                id=track.id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                genre=track.genre,
                genres=[item.genre for item in track.track_genres],
                file_path=track.file_path,
                raw_title=track.raw_title,
                raw_artist=track.raw_artist,
                raw_album=track.raw_album,
                raw_genre=track.raw_genre,
                musicbrainz_recording_id=track.musicbrainz_recording_id,
                lastfm_tags_enriched=track.lastfm_tags_enriched,
                artists=[item.artist_name for item in track.track_artists],
            )
        )

    return response


@router.get("/tracks/{track_id}/stream", tags=["tracks"])
def stream_track(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type, _ = mimetypes.guess_type(str(file_path))
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
    )

@router.post("/tracks/{track_id}/musicbrainz-recording", response_model=TrackResponse, tags=["tracks"])
def fetch_musicbrainz_recording_id(
    track_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    track = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id == track_id)
        .first()
    )

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if track.musicbrainz_recording_id and not force:
        return TrackResponse(
            id=track.id,
            title=track.title,
            artist=track.artist,
            album=track.album,
            genre=track.genre,
            genres=[item.genre for item in track.track_genres],
            file_path=track.file_path,
            raw_title=track.raw_title,
            raw_artist=track.raw_artist,
            raw_album=track.raw_album,
            raw_genre=track.raw_genre,
            musicbrainz_recording_id=track.musicbrainz_recording_id,
            lastfm_tags_enriched=track.lastfm_tags_enriched,
            artists=[item.artist_name for item in track.track_artists],
        )

    mbid = find_recording_mbid(
        track.title,
        track.artist,
        raw_title=track.raw_title,
        raw_artist=track.raw_artist,
    )

    if not mbid:
        raise HTTPException(status_code=404, detail="No MusicBrainz recording match found")

    track.musicbrainz_recording_id = mbid
    db.commit()

    track = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id == track_id)
        .first()
    )

    return TrackResponse(
        id=track.id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        genre=track.genre,
        genres=[item.genre for item in track.track_genres],
        file_path=track.file_path,
        raw_title=track.raw_title,
        raw_artist=track.raw_artist,
        raw_album=track.raw_album,
        raw_genre=track.raw_genre,
        musicbrainz_recording_id=track.musicbrainz_recording_id,
        lastfm_tags_enriched=track.lastfm_tags_enriched,
        artists=[item.artist_name for item in track.track_artists],
    )

@router.post("/tracks/{track_id}/lastfm/now-playing", tags=["tracks"])
def update_track_now_playing_on_lastfm(track_id: int, db: Session = Depends(get_db)):
    settings = db.query(AppSetting).first()

    if not settings:
        raise HTTPException(status_code=400, detail="App settings not found")

    if not settings.lastfm_api_key or not settings.lastfm_api_secret or not settings.lastfm_session_key:
        raise HTTPException(status_code=400, detail="Missing Last.fm credentials or session")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.title or not track.artist:
        raise HTTPException(status_code=400, detail="Track is missing title or artist")

    result = update_now_playing(
        api_key=settings.lastfm_api_key,
        api_secret=settings.lastfm_api_secret,
        session_key=settings.lastfm_session_key,
        track_name=track.title,
        artist_name=track.artist,
        album_name=track.album,
        mbid=track.musicbrainz_recording_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"] or "Last.fm now playing failed")

    return result

@router.post("/tracks/{track_id}/lastfm/scrobble", tags=["tracks"])
def scrobble_track_to_lastfm(track_id: int, db: Session = Depends(get_db)):
    settings = db.query(AppSetting).first()

    if not settings:
        raise HTTPException(status_code=400, detail="App settings not found")

    if not settings.lastfm_api_key or not settings.lastfm_api_secret or not settings.lastfm_session_key:
        raise HTTPException(status_code=400, detail="Missing Last.fm credentials or session")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.title or not track.artist:
        raise HTTPException(status_code=400, detail="Track is missing title or artist")

    result = scrobble_track(
        api_key=settings.lastfm_api_key,
        api_secret=settings.lastfm_api_secret,
        session_key=settings.lastfm_session_key,
        track_name=track.title,
        artist_name=track.artist,
        album_name=track.album,
        mbid=track.musicbrainz_recording_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"] or "Last.fm scrobble failed")

    return result

@router.delete("/tracks/purge", tags=["tracks"])
def purge_tracks(db: Session = Depends(get_db)):
    deleted_tracks = db.query(Track).count()

    db.query(PlaylistTrack).delete()
    db.query(PlaybackQueueItem).delete()

    session = db.query(PlaybackSession).first()
    if session:
        session.current_track_id = None
        session.queue_index = -1
        session.current_time_seconds = 0
        session.is_playing = False

    db.query(TrackArtist).delete()
    db.query(TrackGenre).delete()
    db.query(Track).delete()

    db.commit()

    return {
        "message": "All stored tracks purged",
        "deleted_count": deleted_tracks,
    }


@router.patch("/tracks/{track_id}", response_model=TrackResponse, tags=["tracks"])
def update_track(track_id: int, payload: TrackUpdate, db: Session = Depends(get_db)):
    track = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id == track_id)
        .first()
    )

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    track.title = payload.title
    track.artist = payload.artist
    track.album = payload.album

    if payload.genres is not None:
        normalized_genres = normalize_genre_list(", ".join(payload.genres))
    
        track.genre = normalized_genres[0] if normalized_genres else None
    
        db.query(TrackGenre).filter(
            TrackGenre.track_id == track.id
        ).delete(synchronize_session=False)
    
        for genre_name in normalized_genres:
            db.add(
                TrackGenre(
                    track_id=track.id,
                    genre=genre_name,
                )
            )

    db.commit()
    track = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id == track_id)
        .first()
    )
    db.refresh(track)

    return TrackResponse(
        id=track.id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        genre=track.genre,
        genres=[item.genre for item in track.track_genres],
        file_path=track.file_path,
        raw_title=track.raw_title,
        raw_artist=track.raw_artist,
        raw_album=track.raw_album,
        raw_genre=track.raw_genre,
        musicbrainz_recording_id=track.musicbrainz_recording_id,
        lastfm_tags_enriched=track.lastfm_tags_enriched,
        artists=[item.artist_name for item in track.track_artists],
    )