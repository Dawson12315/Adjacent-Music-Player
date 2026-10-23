from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.radio_station import RadioStation
from app.models.track import Track
from app.models.user import User
from app.routes.tracks import build_track_responses_for_ids
from app.schemas.radio import (
    RadioLineupResponse,
    RadioNextResponse,
    RadioPlayedRequest,
    RadioStationCreate,
    RadioStationResponse,
    RadioTrackResponse,
)
from app.services import radio
from app.services.track_responses import get_artwork_maps, record_artist, resolve_album_artwork
from app.utils.artist_normalization import normalize_artist_name

router = APIRouter()


def _station_or_404(db: Session, station_id: int, user_id: int) -> RadioStation:
    station = (
        db.query(RadioStation)
        .filter(RadioStation.id == station_id, RadioStation.user_id == user_id)
        .first()
    )
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


def _artwork_for(db: Session, station: RadioStation) -> str | None:
    """The seed's picture: the track's record, the album, or the artist."""
    if station.seed_type == "track":
        track = db.query(Track).filter(Track.id == station.seed_track_id).first()
        if track is None:
            return None
        album_map, artist_map = get_artwork_maps(db, [track])
        return resolve_album_artwork(album_map, track.album, record_artist(track)) or artist_map.get(
            normalize_artist_name(track.artist)
        )
    if station.seed_type == "album":
        track = radio._album_tracks_query(db, station.seed_album or "", station.seed_album_artist).first()
        if track is None:
            return None
        album_map, _artist_map = get_artwork_maps(db, [track])
        return resolve_album_artwork(album_map, track.album, record_artist(track))
    track = radio._artist_tracks_query(db, station.seed_artist or "").first()
    if track is None:
        return None
    _album_map, artist_map = get_artwork_maps(db, [track])
    return artist_map.get(normalize_artist_name(station.seed_artist))


def _station_response(db: Session, station: RadioStation) -> RadioStationResponse:
    return RadioStationResponse(
        id=station.id,
        seed_type=station.seed_type,
        seed_track_id=station.seed_track_id,
        seed_album=station.seed_album,
        seed_album_artist=station.seed_album_artist,
        seed_artist=station.seed_artist,
        name=station.name,
        artwork_path=_artwork_for(db, station),
        created_at=station.created_at,
        last_played_at=station.last_played_at,
    )


def _parse_ids(text: str | None) -> list[int]:
    if not text:
        return []
    ids = []
    for part in text.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


@router.post("/radio/stations", response_model=RadioStationResponse, tags=["radio"])
def create_station(
    payload: RadioStationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The listener's station for this seed: made the first time, found
    after that. Starting "Fen radio" twice is one station with one memory."""
    station = radio.get_or_create_station(db, current_user.id, payload)
    if station is None:
        raise HTTPException(status_code=404, detail="Nothing in the library to seed a station from")
    return _station_response(db, station)


@router.get("/radio/stations", response_model=list[RadioStationResponse], tags=["radio"])
def list_stations(
    limit: int = Query(radio.RECENT_STATIONS, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent stations, the one played last first."""
    return [_station_response(db, station) for station in radio.recent_stations(db, current_user.id, limit)]


@router.get("/radio/stations/{station_id}", response_model=RadioStationResponse, tags=["radio"])
def get_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _station_response(db, _station_or_404(db, station_id, current_user.id))


@router.get("/radio/stations/{station_id}/next", response_model=RadioNextResponse, tags=["radio"])
def next_tracks(
    station_id: int,
    limit: int = Query(radio.BATCH, ge=1, le=50),
    # What the client already holds in its queue, comma separated, so the
    # batch does not repeat it before the plays are reported.
    exclude_track_ids: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    station = _station_or_404(db, station_id, current_user.id)
    pairs, thin = radio.next_batch(
        db, station, current_user.id, limit=limit, exclude_track_ids=_parse_ids(exclude_track_ids)
    )
    # Handed out, so remembered: coming back to the station continues this.
    if pairs:
        radio.extend_lineup(db, station, pairs)
    return RadioNextResponse(station=_station_response(db, station), tracks=_radio_tracks(db, pairs), thin=thin)


def _radio_tracks(db: Session, pairs) -> list[RadioTrackResponse]:
    responses = {
        response.id: response
        for response in build_track_responses_for_ids([track_id for track_id, _ in pairs], db)
    }
    tracks = []
    for track_id, reason in pairs:
        base = responses.get(track_id)
        if base is None:
            continue
        tracks.append(RadioTrackResponse(**base.model_dump(), reason=reason))
    return tracks


@router.get("/radio/stations/{station_id}/lineup", response_model=RadioLineupResponse, tags=["radio"])
def station_lineup(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Where the station was left: its lineup from the track the listener
    got to, onward, so a client can continue it without asking the
    recommender. Empty when the station has never played, or its lineup is
    older than ten days."""
    station = _station_or_404(db, station_id, current_user.id)
    pairs = radio.remaining_lineup(station)
    tracks = _radio_tracks(db, pairs)
    return RadioLineupResponse(
        station=_station_response(db, station),
        tracks=tracks,
        resumable=bool(tracks),
        saved_at=station.lineup_saved_at if tracks else None,
    )


@router.post("/radio/stations/{station_id}/played", tags=["radio"])
def report_played(
    station_id: int,
    payload: RadioPlayedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The client says what the station played; those stay out of the next
    two hundred, and the station moves to the top of the recent list."""
    station = _station_or_404(db, station_id, current_user.id)
    radio.record_plays(db, station, payload.track_ids)
    return {"ok": True, "remembered": len(radio.remembered_track_ids(db, station))}


@router.delete("/radio/stations/{station_id}", tags=["radio"])
def delete_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    station = _station_or_404(db, station_id, current_user.id)
    radio.delete_station(db, station)
    return {"ok": True}
