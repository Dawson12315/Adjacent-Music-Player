"""Which of a user's devices is playing, and the rules for changing it.

One account, several devices, one of them playing. The playback session
already holds the queue and the position; this adds the *holder* — the
device whose player is live — and the four things that can happen to it:

  claim     a device starts playing and takes the lease, whoever had it
  report    the holder says where it is; nobody else may
  transfer  the holder (or anyone) hands the lease to a named device,
            queue and position with it
  command   anyone asks the holder to play, pause, skip, seek

The server is the arbiter. The clients obey the `lease` message that
follows every change by pausing when it names someone else; that, and not
any courtesy between clients, is the one-device rule. Fan-out itself lives
in `handoff_hub`; this module is the database half and is synchronous, so it
can be tested without a socket in sight.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.playback_device import PlaybackDevice
from app.models.playback_queue_item import PlaybackQueueItem
from app.models.playback_session import PlaybackSession
from app.models.track import Track
from app.services.playback import get_or_create_playback_session

# A device that has not been heard from for this long is listed greyed and
# cannot be handed the music: nothing would be there to receive it.
AWAY_AFTER_S = 60

# How recently the holder must have reported itself playing for a stream from
# another device to be refused. Short on purpose: a holder whose socket dropped
# stops reporting, and within this window every device may stream again, so a
# stale lease never silences the account. The gate only ever says no while
# another device is demonstrably, currently playing.
STREAM_LEASE_WINDOW_S = 20

# The most queue the server keeps per user: enough for any resume, and
# bounded however large the library is.
MAX_QUEUE_ITEMS = 5000

# Actions a remote may ask of the holder.
COMMANDS = {"play", "pause", "next", "previous", "seek", "shuffle", "repeat", "volume"}


class HandoffError(Exception):
    """A refusal with a code the clients read: 409 unless said otherwise."""

    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class DeviceView:
    device_id: str
    name: str
    kind: str
    platform: str | None
    context: str | None
    online: bool
    last_seen_at: datetime
    is_active: bool

    def payload(self, this_device_id: str | None = None) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "kind": self.kind,
            "platform": self.platform,
            "context": self.context,
            "online": self.online,
            "last_seen_at": self.last_seen_at.isoformat() + "Z",
            "is_active": self.is_active,
            "is_this_device": self.device_id == this_device_id,
        }


# --- devices ------------------------------------------------------------------


def register(db: Session, user_id: int, info: dict, now: datetime | None = None) -> PlaybackDevice:
    """Upsert the device by (user, device_id) and mark it seen."""
    now = now or datetime.utcnow()
    device = (
        db.query(PlaybackDevice)
        .filter(PlaybackDevice.user_id == user_id, PlaybackDevice.device_id == info["device_id"])
        .first()
    )
    if device is None:
        device = PlaybackDevice(user_id=user_id, device_id=info["device_id"], created_at=now)
        db.add(device)

    device.name = info.get("name") or device.name or "Unnamed device"
    device.kind = info.get("kind") or device.kind or "other"
    device.platform = info.get("platform")
    device.app_version = info.get("app_version")
    device.context = info.get("context")
    device.last_seen_at = now
    db.commit()
    db.refresh(device)
    return device


def find_device(db: Session, user_id: int, device_id: str) -> PlaybackDevice | None:
    return (
        db.query(PlaybackDevice)
        .filter(PlaybackDevice.user_id == user_id, PlaybackDevice.device_id == device_id)
        .first()
    )


def require_device(db: Session, user_id: int, device_id: str | None) -> PlaybackDevice:
    """The device behind a request, which must have said hello first."""
    if not device_id:
        raise HandoffError("device_required", "Say which device this is (X-Adjacent-Device).", 400)
    device = find_device(db, user_id, device_id)
    if device is None:
        raise HandoffError("unknown_device", "This device has not introduced itself yet.", 404)
    return device


def touch(db: Session, device: PlaybackDevice, now: datetime | None = None) -> None:
    device.last_seen_at = now or datetime.utcnow()
    db.commit()


def is_online(device: PlaybackDevice, connected: set[str], now: datetime) -> bool:
    if device.device_id in connected:
        return True
    return now - device.last_seen_at <= timedelta(seconds=AWAY_AFTER_S)


def list_devices(
    db: Session, user_id: int, connected: set[str], now: datetime | None = None
) -> list[DeviceView]:
    """Every device this user has used, the live ones first."""
    now = now or datetime.utcnow()
    session = get_or_create_playback_session(db, user_id)
    rows = (
        db.query(PlaybackDevice)
        .filter(PlaybackDevice.user_id == user_id)
        .order_by(PlaybackDevice.last_seen_at.desc())
        .all()
    )
    views = [
        DeviceView(
            device_id=row.device_id,
            name=row.name,
            kind=row.kind,
            platform=row.platform,
            context=row.context,
            online=is_online(row, connected, now),
            last_seen_at=row.last_seen_at,
            is_active=row.id == session.active_device_id,
        )
        for row in rows
    ]
    views.sort(key=lambda view: (not view.is_active, not view.online))
    return views


# --- the state --------------------------------------------------------------


def _window_queue(track_ids: list[int], queue_index: int) -> tuple[list[int], int]:
    if len(track_ids) <= MAX_QUEUE_ITEMS:
        return list(track_ids), queue_index

    index = queue_index if 0 <= queue_index < len(track_ids) else 0
    start = max(0, min(index - MAX_QUEUE_ITEMS // 2, len(track_ids) - MAX_QUEUE_ITEMS))
    window = track_ids[start : start + MAX_QUEUE_ITEMS]

    return list(window), (queue_index - start if 0 <= queue_index < len(track_ids) else -1)


def apply_state(db: Session, session: PlaybackSession, state: dict, now: datetime | None = None) -> bool:
    """Write a full state onto the session. False if it was older than what is there."""
    now = now or datetime.utcnow()
    version = state.get("version")
    if version is not None and session.state_version is not None and version < session.state_version:
        return False

    # "Play all" on a large library sent the whole library: tens of thousands
    # of rows deleted and re-inserted on every debounced save, on the single
    # SQLite writer. Keep a window around the playhead instead.
    queue_ids, queue_index = _window_queue(list(state.get("queue_track_ids") or []), state["queue_index"])

    # Only ids that exist: a track cleanup removed since the client last
    # loaded used to fail the whole save with a foreign-key 500.
    if queue_ids:
        existing = {row[0] for row in db.query(Track.id).filter(Track.id.in_(queue_ids)).all()}
        kept = [track_id for track_id in queue_ids if track_id in existing]
        if len(kept) != len(queue_ids):
            dropped_before = sum(1 for track_id in queue_ids[:queue_index] if track_id not in existing)
            queue_index = max(-1, queue_index - dropped_before)
            queue_ids = kept

    current_track_id = state.get("current_track_id")
    if current_track_id is not None and db.get(Track, current_track_id) is None:
        current_track_id = None

    session.current_track_id = current_track_id
    session.queue_index = queue_index
    session.current_time_seconds = int(state.get("current_time_seconds") or 0)
    session.is_playing = bool(state.get("is_playing"))
    session.is_shuffle = bool(state.get("is_shuffle"))
    session.is_loop = bool(state.get("is_loop"))
    session.source_type = state.get("source_type")
    session.source_id = state.get("source_id")
    session.state_version = version if version is not None else (session.state_version or 0) + 1
    session.reported_at = now

    stored_ids = [item.track_id for item in session.queue_items]

    if stored_ids != queue_ids:
        db.query(PlaybackQueueItem).filter(PlaybackQueueItem.session_id == session.id).delete(
            synchronize_session=False
        )
        for position, track_id in enumerate(queue_ids):
            db.add(PlaybackQueueItem(session_id=session.id, track_id=track_id, position=position))

    db.commit()
    db.refresh(session)
    return True


def apply_position(db: Session, session: PlaybackSession, report: dict, now: datetime | None = None) -> bool:
    """The cheap write: position and flags, the queue untouched."""
    now = now or datetime.utcnow()
    version = report.get("version")
    if version is not None and session.state_version is not None and version < session.state_version:
        return False

    if report.get("current_track_id") is not None:
        if db.get(Track, report["current_track_id"]) is not None:
            session.current_track_id = report["current_track_id"]
    if report.get("queue_index") is not None:
        session.queue_index = int(report["queue_index"])
    session.current_time_seconds = int(report.get("current_time_seconds") or 0)
    session.is_playing = bool(report.get("is_playing"))
    if report.get("is_shuffle") is not None:
        session.is_shuffle = bool(report["is_shuffle"])
    if report.get("is_loop") is not None:
        session.is_loop = bool(report["is_loop"])
    session.state_version = version if version is not None else (session.state_version or 0) + 1
    session.reported_at = now
    db.commit()
    return True


def state_payload(session: PlaybackSession) -> dict:
    return {
        "current_track_id": session.current_track_id,
        "queue_index": session.queue_index,
        "current_time_seconds": session.current_time_seconds,
        "is_playing": session.is_playing,
        "is_shuffle": session.is_shuffle,
        "is_loop": session.is_loop,
        "queue_track_ids": [item.track_id for item in session.queue_items],
        "source_type": session.source_type,
        "source_id": session.source_id,
        "version": session.state_version,
        "reported_at": session.reported_at.isoformat() + "Z" if session.reported_at else None,
    }


def position_payload(session: PlaybackSession) -> dict:
    """What the rest of the devices need on every tick: no queue."""
    return {
        "current_track_id": session.current_track_id,
        "queue_index": session.queue_index,
        "current_time_seconds": session.current_time_seconds,
        "is_playing": session.is_playing,
        "is_shuffle": session.is_shuffle,
        "is_loop": session.is_loop,
        "version": session.state_version,
        "reported_at": session.reported_at.isoformat() + "Z" if session.reported_at else None,
    }


# --- the lease --------------------------------------------------------------


def holder(db: Session, session: PlaybackSession) -> PlaybackDevice | None:
    if session.active_device_id is None:
        return None
    return db.get(PlaybackDevice, session.active_device_id)


def lease_payload(
    db: Session, session: PlaybackSession, connected: set[str], now: datetime | None = None, with_state: bool = True
) -> dict:
    now = now or datetime.utcnow()
    active = holder(db, session)
    online = bool(active) and is_online(active, connected, now)
    return {
        "active_device_id": active.device_id if active else None,
        "active_device_name": active.name if active else None,
        "since": session.active_since.isoformat() + "Z" if session.active_since else None,
        # A holder nobody can reach is not really playing: remotes show the
        # state but offer "Play here" rather than transport buttons.
        "stale": bool(active) and not online,
        "state": state_payload(session) if with_state else position_payload(session),
    }


def claim(
    db: Session, user_id: int, device: PlaybackDevice, state: dict | None, now: datetime | None = None
) -> PlaybackSession:
    """This device is playing now. Whoever held the lease loses it."""
    now = now or datetime.utcnow()
    session = get_or_create_playback_session(db, user_id)
    if session.active_device_id != device.id:
        session.active_device_id = device.id
        session.active_since = now
    device.last_seen_at = now
    if state is not None:
        apply_state(db, session, state, now)
    else:
        db.commit()
        db.refresh(session)
    return session


def report(
    db: Session, user_id: int, device: PlaybackDevice, state: dict, now: datetime | None = None, full: bool = False
) -> PlaybackSession:
    """The holder saying where it is. Anyone else is told who holds it."""
    now = now or datetime.utcnow()
    session = get_or_create_playback_session(db, user_id)
    if session.active_device_id is None:
        # Nobody holds it: a report is as good as a claim. A device that
        # was playing when the server restarted keeps the music without
        # having to notice.
        session.active_device_id = device.id
        session.active_since = now
    elif session.active_device_id != device.id:
        raise HandoffError("device_not_active", "Another device is playing.")
    device.last_seen_at = now
    if full:
        apply_state(db, session, state, now)
    else:
        apply_position(db, session, state, now)
    return session


def transfer(
    db: Session,
    user_id: int,
    from_device: PlaybackDevice,
    to_device_id: str,
    state: dict | None,
    connected: set[str],
    now: datetime | None = None,
) -> tuple[PlaybackSession, PlaybackDevice]:
    """Hand the lease to a named device. The music follows in `take_over`."""
    now = now or datetime.utcnow()
    target = find_device(db, user_id, to_device_id)
    if target is None:
        raise HandoffError("unknown_device", "That device has not been seen.", 404)
    if not is_online(target, connected, now):
        raise HandoffError("device_away", f"{target.name} is not reachable right now.")

    session = get_or_create_playback_session(db, user_id)
    if state is not None and (session.active_device_id in (None, from_device.id)):
        # The sender's state is the freshest there is when it holds the lease
        # (or nobody does); a remote handing the music on carries nothing.
        apply_state(db, session, state, now)

    session.active_device_id = target.id
    session.active_since = now
    from_device.last_seen_at = now
    db.commit()
    db.refresh(session)
    return session, target


def release(db: Session, user_id: int, device: PlaybackDevice, now: datetime | None = None) -> PlaybackSession | None:
    """The holder bowing out (a tab closing, `bye`): the lease goes spare, paused."""
    session = get_or_create_playback_session(db, user_id)
    if session.active_device_id != device.id:
        return None
    session.active_device_id = None
    session.active_since = None
    session.is_playing = False
    session.reported_at = now or datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


# --- the stream lease (hard enforcement) ------------------------------------


def stream_allowed(db: Session, user_id: int, device_id: str | None, now: datetime | None = None) -> bool:
    """Whether this device may be served a stream right now.

    Fail open in every ambiguous case — the gate must never be the reason the
    music will not play for the device that is actually meant to be playing it.
    It says no only when another device holds the lease and reported itself
    playing within the last few seconds, and this is not that device.
    """
    if not device_id:
        return True  # an old client, or a download/artwork request: not gated

    now = now or datetime.utcnow()
    session = (
        db.query(PlaybackSession)
        .filter(PlaybackSession.user_id == user_id)
        .first()
    )
    if session is None or session.active_device_id is None:
        return True  # nobody holds the lease

    holder = db.get(PlaybackDevice, session.active_device_id)
    if holder is None:
        return True  # the lease points at nothing

    if holder.device_id == device_id:
        return True  # this device *is* the holder

    if not session.is_playing:
        return True  # the holder is paused; a second device may start

    if session.reported_at is None:
        return True  # the holder never said where it is

    # The holder is another device, playing, and heard from recently: refuse.
    return now - session.reported_at > timedelta(seconds=STREAM_LEASE_WINDOW_S)
