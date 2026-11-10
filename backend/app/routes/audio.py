"""Audio analysis: what the server has heard in the library, and an admin's
say over a track's flags.

* GET  /audio/status          coverage and the worker, for the Settings card
* POST /audio/analyse         queue the backlog now rather than tonight
* PUT  /tracks/{id}/flags     an admin sets vocal / language / explicit
* DELETE /tracks/{id}/flags   back to detected, and listen again
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_admin
from app.models.track import Track
from app.models.user import User
from app.services import audio_analysis, track_flags

logger = logging.getLogger(__name__)
router = APIRouter()


class FlagsUpdate(BaseModel):
    """Fields left out are left alone; an explicit null clears one."""

    vocal_state: Optional[str] = Field(default=None, pattern="^(vocal|instrumental)$")
    language: Optional[str] = Field(default=None, max_length=8)
    explicit_state: Optional[str] = Field(default=None, pattern="^(explicit|clean)$")


def _track_or_404(db: Session, track_id: int) -> Track:
    track = db.query(Track).filter(Track.id == track_id).first()
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return track


@router.get("/audio/status", tags=["audio"])
def audio_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    enabled, at, _model = audio_analysis.analysis_settings()
    response = JSONResponse(
        content={
            **audio_analysis.coverage(db),
            "analysis": {"enabled": enabled, "time": at, **audio_analysis.get_progress()},
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/audio/analyse", tags=["audio"], status_code=202)
def analyse_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Start on the backlog now, most-played first, within the nightly
    budget. 409 when analysis is off or nothing on this server can measure."""
    enabled, _at, _model = audio_analysis.analysis_settings()
    if not enabled:
        raise HTTPException(status_code=409, detail={"code": "analysis_off", "message": "Audio analysis is turned off in Settings."})
    if not audio_analysis.anything_to_measure_with():
        raise HTTPException(status_code=409, detail={"code": "unsupported", "message": "This server cannot analyse audio."})
    queued = audio_analysis.enqueue_backlog()
    return {"queued": queued, **audio_analysis.get_progress()}


@router.put("/tracks/{track_id}/flags", tags=["audio"])
def put_flags(
    track_id: int,
    payload: FlagsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """An admin's word on a track's flags; the server then leaves the track
    alone. Send only the fields to change."""
    track = _track_or_404(db, track_id)
    given = payload.model_dump(exclude_unset=True)
    if not given:
        raise HTTPException(status_code=422, detail="Nothing to change.")
    try:
        track_flags.set_by_admin(
            db,
            track,
            vocal_state=given.get("vocal_state", ...),
            language=given.get("language", ...),
            explicit_state=given.get("explicit_state", ...),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    logger.info("Flags for track %s set by %s: %s", track_id, current_user.username, given)
    return track_flags.flags_payload(track)


@router.delete("/tracks/{track_id}/flags", tags=["audio"])
def reset_flags(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Forget the admin's word and what was detected, and listen again."""
    track = _track_or_404(db, track_id)
    track.vocal_state = None
    track.language = None
    track.language_confidence = None
    track.explicit_state = None
    track.flags_set_by = None
    track.flags_checked_at = None
    db.commit()
    audio_analysis.request_analysis(track_id, front=True)
    return track_flags.flags_payload(track)
