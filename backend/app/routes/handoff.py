"""Device handoff: the socket, and the HTTP twins of everything it carries.

The socket (`/playback/ws`) is how a live client hears about a lease change
the instant it happens. The twins exist for the clients that cannot hold a
socket — a proxy without WebSocket support, the Android playback service with
the app swiped away — which poll `GET /playback/devices` and act over HTTP,
getting the same one-device rule a beat slower.

The rules live in `app.services.handoff`, which is synchronous and does the
database work; this module runs that work off the event loop with
`run_in_threadpool`, then fans the result out through `app.services.handoff_hub`.
"""

import asyncio
import contextlib
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Response, WebSocket, status
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db import SessionLocal, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.handoff import (
    ClaimBody,
    CommandBody,
    DeviceInfo,
    PositionReport,
    TransferBody,
)
from app.schemas.playback import PlaybackStateUpdate
from app.services import handoff
from app.services.auth import decode_access_token, get_user_by_id, password_fingerprint
from app.services.handoff import HandoffError
from app.services.handoff_hub import hub
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()

# How long the client has to say hello before the socket is closed.
HELLO_TIMEOUT_S = 5
# Server-side keepalive: a ping this often, and the socket closed once the
# device has been silent for this long. A suspended phone stops answering,
# and within about half a minute it is no longer a device the music can be
# handed to — the socket itself may look open for far longer than that.
PING_INTERVAL_S = 10
SILENT_CLOSE_AFTER_S = 30

DEVICE_HEADER = "X-Adjacent-Device"


# --- authentication ---------------------------------------------------------


def _user_from_token(db: Session, token: str | None) -> User | None:
    """The same checks as get_current_user, without the HTTP machinery.

    A websocket cannot raise an HTTPException to a browser usefully; the caller
    closes with a code instead. Stream tokens (which carry a purpose) are
    refused here too, so a leaked stream URL cannot open a control socket.
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub") or payload.get("purpose"):
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        return None
    fingerprint = payload.get("pwd")
    if fingerprint and fingerprint != password_fingerprint(user.password_hash):
        return None
    # A one-time-password account may not drive playback: it may only reach the
    # four routes that let it choose a password.
    if user.must_change_password:
        return None
    return user


# --- fan-out helpers (shared by the socket and the twins) --------------------


async def _after_claim(user_id: int, this_device_id: str) -> None:
    """Tell everyone the lease moved: the rest so they pause, the claimer so
    it hears the version the server settled on. A fresh client's counter
    starts low, and without the echo its next report could read as stale."""
    connected = hub.connected_device_ids(user_id)
    lease = await run_in_threadpool(_lease_dict, user_id, connected, False)
    await hub.broadcast(user_id, {"type": "lease", **lease})


async def _after_report(user_id: int, this_device_id: str, full: bool) -> None:
    """Fan the holder's new position (or full state) out to the rest."""
    connected = hub.connected_device_ids(user_id)
    lease = await run_in_threadpool(_lease_dict, user_id, connected, full)
    await hub.broadcast(user_id, {"type": "state", **lease["state"]}, exclude=this_device_id)


async def _after_transfer(user_id: int, target_device_id: str, from_device_id: str) -> None:
    """Send the chosen device the music, and tell the rest who holds it now."""
    connected = hub.connected_device_ids(user_id)
    lease = await run_in_threadpool(_lease_dict, user_id, connected, True)
    await hub.send(user_id, target_device_id, {"type": "take_over", "state": lease["state"]})
    # The target included: it learns it is the holder from the lease frame as
    # well as from the take_over, so its reports go out as the holder's even
    # on a client that reads only one of the two.
    await hub.broadcast(user_id, {"type": "lease", **lease})


def _lease_dict(user_id: int, connected: set[str], with_state: bool) -> dict:
    db = SessionLocal()
    try:
        session = handoff.get_or_create_playback_session(db, user_id)
        return handoff.lease_payload(db, session, connected, with_state=with_state)
    finally:
        db.close()


def _devices_dict(user_id: int, connected: set[str], this_device_id: str | None) -> dict:
    db = SessionLocal()
    try:
        return _devices_dict_sync(db, user_id, connected, this_device_id)
    finally:
        db.close()


# --- the socket --------------------------------------------------------------


def _origin_allowed(origin: str | None, host: str | None) -> bool:
    """Whether a browser's Origin may open the control socket.

    A browser always sends one; the apps send none, and a missing origin is
    allowed. One that is present must be a configured front-end origin or the
    server's own host — the same allowance CORS gives the HTTP routes, which
    the WebSocket handshake does not go through. The cookie is SameSite=Lax,
    which already keeps a cross-site page from carrying it; this closes the
    remaining case of a browser configured to send it anyway.
    """
    if not origin:
        return True
    allowed = set(settings.frontend_origins)
    if not settings.is_production:
        allowed.add("http://localhost:5173")
    if origin.rstrip("/") in allowed:
        return True
    try:
        origin_host = origin.split("://", 1)[1].split("/", 1)[0]
    except IndexError:
        return False
    return bool(host) and origin_host.lower() == host.lower()


@router.websocket("/playback/ws")
async def playback_socket(websocket: WebSocket) -> None:
    if not _origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host")):
        await websocket.close(code=4403)
        return

    token = websocket.cookies.get(settings.auth_cookie_name)
    auth_db = SessionLocal()
    try:
        user = await run_in_threadpool(_user_from_token, auth_db, token)
    finally:
        auth_db.close()

    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    user_id = user.id
    device_id: str | None = None
    ping_task: asyncio.Task | None = None
    # Only an explicit bye gives the lease up. A dropped socket — a network
    # blink, a proxy idle close, the app reopening its own connection — kept
    # releasing it, and the reconnect then told the device nobody was playing,
    # which it took as its cue to pause the music it was playing.
    said_bye = False

    try:
        # The first frame must be a hello, soon.
        try:
            first = await asyncio.wait_for(websocket.receive_json(), timeout=HELLO_TIMEOUT_S)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001
            await websocket.close(code=4400)
            return

        if first.get("type") != "hello":
            await websocket.close(code=4400)
            return

        try:
            info = DeviceInfo(**{k: v for k, v in first.items() if k != "type"})
        except Exception:  # noqa: BLE001
            await websocket.close(code=4400)
            return

        device_id = info.device_id
        async with hub.lock(user_id):
            await run_in_threadpool(_register, user_id, info.model_dump())
            await hub.attach(user_id, device_id, websocket)
            devices = await run_in_threadpool(
                _devices_dict, user_id, hub.connected_device_ids(user_id), device_id
            )
        await websocket.send_json({"type": "devices", **devices})

        ping_task = asyncio.create_task(_ping_loop(websocket, user_id, device_id))

        while True:
            frame = await websocket.receive_json()
            if await _dispatch(websocket, user_id, device_id, frame) == "bye":
                said_bye = True
                break
    except Exception:  # noqa: BLE001 — a disconnect arrives as an exception
        pass
    finally:
        if ping_task is not None:
            ping_task.cancel()
            # CancelledError is a BaseException, so suppress it by name — a bare
            # suppress(Exception) lets it escape into the portal and surface at
            # the socket's close.
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await ping_task
        if device_id is not None:
            async with hub.lock(user_id):
                hub.detach(user_id, device_id, websocket)
                # A device that already reconnected on a newer socket has not
                # left; its old handler must not take its lease away.
                reconnected = hub.is_connected(user_id, device_id)
                released = (
                    await run_in_threadpool(_release, user_id, device_id)
                    if said_bye and not reconnected
                    else False
                )
            if released:
                await _after_claim(user_id, device_id)  # lease went spare: others learn of it


async def _ping_loop(websocket: WebSocket, user_id: int, device_id: str) -> None:
    """Ping on a schedule; close the socket once the device stops answering.

    Closing it is what lets the handler's `finally` run and the hub forget
    the socket. The lease is not released by this — a device that fell
    asleep mid-song keeps its place and simply reconnects — but it stops
    being a device anyone is offered to hand the music to.
    """
    while True:
        await asyncio.sleep(PING_INTERVAL_S)
        if hub.silent_for(user_id, device_id) > SILENT_CLOSE_AFTER_S:
            with contextlib.suppress(Exception):
                await websocket.close(code=4002)
            return
        await websocket.send_json({"type": "ping"})


async def _dispatch(websocket: WebSocket, user_id: int, device_id: str, frame: dict) -> None:
    kind = frame.get("type")
    try:
        if kind == "pong":
            hub.note_pong(user_id, device_id)
            return
        if kind == "hello":
            info = DeviceInfo(**{k: v for k, v in frame.items() if k != "type"})
            await run_in_threadpool(_register, user_id, info.model_dump())
            return
        if kind == "claim":
            state = ClaimBody(**{k: v for k, v in frame.items() if k != "type"}).state.model_dump()
            async with hub.lock(user_id):
                await run_in_threadpool(_claim, user_id, device_id, state)
            await _after_claim(user_id, device_id)
            return
        if kind == "state":
            full = bool(frame.get("full"))
            raw = {k: v for k, v in frame.items() if k not in ("type", "full")}
            # The same shapes the HTTP twins validate: a frame with a string
            # where a number goes is an error back to the sender, not a
            # traceback in the handler.
            report = (PlaybackStateUpdate(**raw) if full else PositionReport(**raw)).model_dump()
            async with hub.lock(user_id):
                took_spare = await run_in_threadpool(_report, user_id, device_id, report, full)
            # A report that found the lease spare took it: say so, or remotes
            # keep showing nothing playing.
            if took_spare:
                await _after_claim(user_id, device_id)
            await _after_report(user_id, device_id, full)
            return
        if kind == "transfer":
            body = TransferBody(**{k: v for k, v in frame.items() if k != "type"})
            state = body.state.model_dump() if body.state else None
            async with hub.lock(user_id):
                await run_in_threadpool(_transfer, user_id, device_id, body.to, state)
            await _after_transfer(user_id, body.to, device_id)
            return
        if kind == "command":
            body = CommandBody(**{k: v for k, v in frame.items() if k != "type"})
            await _forward_command(user_id, device_id, body)
            return
        if kind == "bye":
            await websocket.close(code=1000)
            return "bye"
    except HandoffError as error:
        await websocket.send_json({"type": "error", "code": error.code, "message": error.message})
    except Exception:  # noqa: BLE001
        logger.exception("handoff frame failed")
        await websocket.send_json({"type": "error", "code": "bad_frame", "message": "Could not handle that."})


async def _forward_command(user_id: int, from_device_id: str, body: CommandBody) -> None:
    holder_device_id = await run_in_threadpool(_holder_device_id, user_id)
    if holder_device_id is None:
        raise HandoffError("nobody_active", "Nothing is playing to control.")
    if holder_device_id == from_device_id:
        return  # a device does not command itself; it just does the thing
    await hub.send(user_id, holder_device_id, {"type": "command", "action": body.action, "args": body.args})


# --- threadpool bodies (one DB session each) --------------------------------


def _register(user_id: int, info: dict) -> None:
    db = SessionLocal()
    try:
        handoff.register(db, user_id, info)
    finally:
        db.close()


def _claim(user_id: int, device_id: str, state: dict | None) -> None:
    db = SessionLocal()
    try:
        device = handoff.require_device(db, user_id, device_id)
        handoff.claim(db, user_id, device, state)
    finally:
        db.close()


def _report(user_id: int, device_id: str, report: dict, full: bool) -> bool:
    """Apply the report; True if it took a spare lease on the way."""
    db = SessionLocal()
    try:
        device = handoff.require_device(db, user_id, device_id)
        session = handoff.report(db, user_id, device, report, full=full)
        return bool(getattr(session, "took_spare_lease", False))
    finally:
        db.close()


def _transfer(user_id: int, from_device_id: str, to_device_id: str, state: dict | None) -> None:
    db = SessionLocal()
    try:
        connected = hub.connected_device_ids(user_id)
        from_device = handoff.require_device(db, user_id, from_device_id)
        handoff.transfer(db, user_id, from_device, to_device_id, state, connected)
    finally:
        db.close()


def _release(user_id: int, device_id: str) -> bool:
    db = SessionLocal()
    try:
        device = handoff.find_device(db, user_id, device_id)
        if device is None:
            return False
        return handoff.release(db, user_id, device) is not None
    finally:
        db.close()


def _holder_device_id(user_id: int) -> str | None:
    db = SessionLocal()
    try:
        session = handoff.get_or_create_playback_session(db, user_id)
        device = handoff.holder(db, session)
        return device.device_id if device else None
    finally:
        db.close()


# --- the HTTP twins ----------------------------------------------------------


def _device_header(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="Missing X-Adjacent-Device header.")
    return value


def _raise(error: HandoffError) -> None:
    raise HTTPException(status_code=error.status, detail={"message": error.message, "code": error.code})


# The twins that read the hub are async: the hub is the event loop's, and a
# plain `def` route runs in a worker thread, where touching its dicts raced
# the socket handlers.


@router.post("/playback/devices/hello", tags=["handoff"])
async def http_hello(
    info: DeviceInfo,
    current_user: User = Depends(get_current_user),
):
    connected = hub.connected_device_ids(current_user.id)
    return await run_in_threadpool(_hello_sync, current_user.id, info.model_dump(), connected)


def _hello_sync(user_id: int, info: dict, connected: set[str]) -> dict:
    db = SessionLocal()
    try:
        handoff.register(db, user_id, info)
        return _devices_dict_sync(db, user_id, connected, info["device_id"])
    finally:
        db.close()


@router.get("/playback/devices", tags=["handoff"])
async def http_devices(
    current_user: User = Depends(get_current_user),
    x_adjacent_device: str | None = Header(default=None),
):
    connected = hub.connected_device_ids(current_user.id)
    result = await run_in_threadpool(_devices_poll_sync, current_user.id, x_adjacent_device, connected)
    # A polling device collects anything that was waiting for it.
    if x_adjacent_device:
        result["pending_commands"] = hub.drain_pending(current_user.id, x_adjacent_device)
    return result


def _devices_poll_sync(user_id: int, this_device_id: str | None, connected: set[str]) -> dict:
    db = SessionLocal()
    try:
        if this_device_id:
            device = handoff.find_device(db, user_id, this_device_id)
            if device is not None:
                handoff.touch(db, device)
        return _devices_dict_sync(db, user_id, connected, this_device_id)
    finally:
        db.close()


@router.post("/playback/claim", tags=["handoff"])
async def http_claim(
    body: ClaimBody,
    current_user: User = Depends(get_current_user),
    x_adjacent_device: str | None = Header(default=None),
):
    device_id = _device_header(x_adjacent_device)
    try:
        async with hub.lock(current_user.id):
            await run_in_threadpool(_claim, current_user.id, device_id, body.state.model_dump())
        await _after_claim(current_user.id, device_id)
    except HandoffError as error:
        _raise(error)
    return {"ok": True}


@router.post("/playback/state", tags=["handoff"])
async def http_state(
    report: PositionReport,
    current_user: User = Depends(get_current_user),
    x_adjacent_device: str | None = Header(default=None),
):
    device_id = _device_header(x_adjacent_device)
    try:
        async with hub.lock(current_user.id):
            took_spare = await run_in_threadpool(_report, current_user.id, device_id, report.model_dump(), False)
        if took_spare:
            await _after_claim(current_user.id, device_id)
        await _after_report(current_user.id, device_id, False)
    except HandoffError as error:
        _raise(error)
    return {"ok": True}


@router.post("/playback/transfer", tags=["handoff"])
async def http_transfer(
    body: TransferBody,
    current_user: User = Depends(get_current_user),
    x_adjacent_device: str | None = Header(default=None),
):
    device_id = _device_header(x_adjacent_device)
    state = body.state.model_dump() if body.state else None
    try:
        async with hub.lock(current_user.id):
            await run_in_threadpool(_transfer, current_user.id, device_id, body.to, state)
        await _after_transfer(current_user.id, body.to, device_id)
    except HandoffError as error:
        _raise(error)
    return {"ok": True}


@router.post("/playback/command", tags=["handoff"])
async def http_command(
    body: CommandBody,
    current_user: User = Depends(get_current_user),
    x_adjacent_device: str | None = Header(default=None),
):
    device_id = _device_header(x_adjacent_device)
    try:
        await _forward_command(current_user.id, device_id, body)
    except HandoffError as error:
        _raise(error)
    return {"ok": True}


def _devices_dict_sync(db: Session, user_id: int, connected: set[str], this_device_id: str | None) -> dict:
    views = handoff.list_devices(db, user_id, connected)
    session = handoff.get_or_create_playback_session(db, user_id)
    # The position, not the queue: a polling tab asked for this every fifteen
    # seconds and got up to five thousand track ids each time. The queue
    # travels once, in the take_over that hands the music to a device.
    lease = handoff.lease_payload(db, session, connected, with_state=False)
    return {
        "devices": [view.payload(this_device_id) for view in views],
        "lease": lease,
    }
