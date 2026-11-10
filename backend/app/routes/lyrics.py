"""Lyrics for a track: read, correct, and ask the server to produce them."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.track import Track
from app.models.track_lyrics import TrackLyrics
from app.models.user import User
from app.schemas.lyrics import LyricsResponse, LyricsUpdate
from app.services import lyrics_runner
from app.services.lyrics_files import lyrics_from_file, parse_lrc

logger = logging.getLogger(__name__)

router = APIRouter()


def lyrics_response(row: TrackLyrics) -> dict:
    synced = None
    if row.synced:
        try:
            synced = [{"t": float(at), "line": str(line)} for at, line in json.loads(row.synced)]
        except (ValueError, TypeError):
            synced = None
    return {
        "track_id": row.track_id,
        "source": row.source,
        "synced_source": row.synced_source,
        "plain": row.plain,
        "synced": synced,
        "language": row.language,
        "generated": row.source == "transcribed" or row.synced_source in ("aligned", "transcribed"),
        "model": row.model,
        "confidence": row.confidence,
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
    }


def _track_or_404(db: Session, track_id: int) -> Track:
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track


def _no_lyrics(track_id: int) -> JSONResponse:
    status = lyrics_runner.track_generation_status(track_id)
    return JSONResponse(
        status_code=404,
        content={"detail": {"code": "no_lyrics", "message": "No lyrics for this track.", "generation": status}},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/tracks/{track_id}/lyrics", response_model=LyricsResponse, tags=["lyrics"])
def get_lyrics(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The track's lyrics. 404 with a `generation` status when it has none,
    so a client knows whether asking the server to produce them is an option."""
    _track_or_404(db, track_id)
    row = db.query(TrackLyrics).filter(TrackLyrics.track_id == track_id).first()
    if row is None:
        return _no_lyrics(track_id)
    return lyrics_response(row)


@router.post("/tracks/{track_id}/lyrics/generate", tags=["lyrics"], status_code=202)
def generate_lyrics(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ask the server to produce lyrics for this track — timing for words it
    already has, or words and timing from the audio. Queued at the front;
    the client polls the lyrics route until they appear."""
    _track_or_404(db, track_id)
    row = db.query(TrackLyrics).filter(TrackLyrics.track_id == track_id).first()
    if row is not None and row.synced:
        return {"state": "done", "reason": None}
    status = lyrics_runner.request_generation(track_id, front=True)
    if status["state"] in ("off", "unsupported"):
        raise HTTPException(status_code=409, detail={"code": f"generation_{status['state']}", "message": status["reason"]})
    return status


@router.put("/tracks/{track_id}/lyrics", response_model=LyricsResponse, tags=["lyrics"])
def put_lyrics(
    track_id: int,
    payload: LyricsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Typed, pasted or corrected lyrics. A person's words outrank every
    other source and are never overwritten by a scan."""
    _track_or_404(db, track_id)

    plain = (payload.plain or "").replace("\r", "").strip()
    synced = [[line.t, " ".join(line.line.split())] for line in (payload.synced or []) if line.line.strip()]

    if plain and not synced:
        parsed = parse_lrc(plain)
        plain = parsed["plain"]
        synced = parsed["synced"] or []
    if not plain and synced:
        plain = "\n".join(line for _at, line in synced)
    if not plain:
        raise HTTPException(status_code=422, detail="Lyrics cannot be empty.")

    row = db.query(TrackLyrics).filter(TrackLyrics.track_id == track_id).first()
    if row is None:
        row = TrackLyrics(track_id=track_id)
        db.add(row)
    row.source = "user"
    row.synced_source = "user" if synced else None
    row.plain = plain
    row.synced = json.dumps(synced, ensure_ascii=False) if synced else None
    row.model = None
    row.confidence = None
    db.commit()
    db.refresh(row)
    logger.info("Lyrics for track %s edited by %s", track_id, current_user.username)
    return lyrics_response(row)


@router.delete("/tracks/{track_id}/lyrics", tags=["lyrics"])
def delete_lyrics(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Drop what Adjacent holds for this track and read the file again, so a
    correction can be undone and a generated text thrown away."""
    track = _track_or_404(db, track_id)
    db.query(TrackLyrics).filter(TrackLyrics.track_id == track_id).delete(synchronize_session=False)
    db.commit()

    found = lyrics_from_file(track.file_path)
    if found:
        row = TrackLyrics(
            track_id=track_id,
            source=found["source"],
            synced_source=found["source"] if found["synced"] else None,
            plain=found["plain"],
            synced=json.dumps(found["synced"], ensure_ascii=False) if found["synced"] else None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return lyrics_response(row)
    return _no_lyrics(track_id)


@router.get("/lyrics/status", tags=["lyrics"])
def lyrics_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """For the Settings card: how many tracks have words and from where, and
    what the generation worker is doing."""
    from sqlalchemy import func

    counts = dict(
        db.query(TrackLyrics.source, func.count(TrackLyrics.id)).group_by(TrackLyrics.source).all()
    )
    timed = db.query(func.count(TrackLyrics.id)).filter(TrackLyrics.synced.isnot(None)).scalar() or 0
    total_tracks = db.query(func.count(Track.id)).filter(Track.missing_since.is_(None)).scalar() or 0
    enabled, model = lyrics_runner.generation_settings()
    response = JSONResponse(
        content={
            "tracks": total_tracks,
            "with_lyrics": int(sum(counts.values())),
            "timed": int(timed),
            "by_source": {key: int(value) for key, value in counts.items()},
            "generation": {"enabled": enabled, "model": model, **lyrics_runner.get_progress()},
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response
