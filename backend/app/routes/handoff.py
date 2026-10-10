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
from app.services import handoff
from app.services.auth import decode_access_token, get_user_by_id, password_fingerprint
from app.services.handoff import HandoffError
from app.services.handoff_hub import hub
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()

# How long the client has to say hello before the socket is closed.
HELLO_TIMEOUT_S = 5
# Server-side keepalive: a ping this often, and a socket closed after this
# many go unanswered.
PING_INTERVAL_S = 25

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
    """Tell everyone else they just lost the lease, so they pause."""
    connected = hub.connected_device_ids(user_id)
    lease = await run_in_threadpool(_lease_dict, user_id, connected, False)
    await hub.broadcast(user_id, {"type": "lease", **lease}, exclude=this_device_id)


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
    await hub.broadcast(user_id, {"type": "lease", **lease}, exclude=target_device_id)


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
        views = handoff.list_devices(db, user_id, connected)
        session = handoff.get_or_create_playback_session(db, user_id)
        lease = handoff.lease_payload(db, session, connected)
        return {
            "devices": [view.payload(this_device_id) for view in views],
            "lease": lease,
        }
    finally:
        db.close()


# --- the socket --------------------------------------------------------------


@router.websocket("/playback/ws")
async def playback_socket(websocket: WebSocket) -> None:
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

        ping_task = asyncio.create_task(_ping_loop(websocket))

        while True:
            frame = await websocket.receive_json()
            await _dispatch(websocket, user_id, device_id, frame)
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
                released = await run_in_threadpool(_release, user_id, device_id)
            if released:
                await _after_claim(user_id, device_id)  # lease went spare: others learn of it


async def _ping_loop(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(PING_INTERVAL_S)
        await websocket.send_json({"type": "ping"})


async def _dispatch(websocket: WebSocket, user_id: int, device_id: str, frame: dict) -> None:
    kind = frame.get("type")
    try:
        if kind == "pong":
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
            report = {k: v for k, v in frame.items() if k not in ("type", "full")}
            async with hub.lock(user_id):
                accepted = await run_in_threadpool(_report, user_id, device_id, report, full)
            if accepted:
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
            return
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
    db = SessionLocal()
    try:
        device = handoff.require_device(db, user_id, device_id)
        handoff.report(db, user_id, device, report, full=full)
        return True
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


@router.post("/playback/devices/hello", tags=["handoff"])
def http_hello(
    info: DeviceInfo,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    handoff.register(db, current_user.id, info.model_dump())
    connected = hub.connected_device_ids(current_user.id)
    return _devices_dict_sync(db, current_user.id, connected, info.device_id)


@router.get("/playback/devices", tags=["handoff"])
def http_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_adjacent_device: str | None = Header(default=None),
):
    connected = hub.connected_device_ids(current_user.id)
    if x_adjacent_device:
        device = handoff.find_device(db, current_user.id, x_adjacent_device)
        if device is not None:
            handoff.touch(db, device)
    result = _devices_dict_sync(db, current_user.id, connected, x_adjacent_device)
    # A polling device collects anything that was waiting for it.
    if x_adjacent_device:
        result["pending_commands"] = hub.drain_pending(current_user.id, x_adjacent_device)
    return result


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
            await run_in_threadpool(_report, current_user.id, device_id, report.model_dump(), False)
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
    lease = handoff.lease_payload(db, session, connected)
    return {
        "devices": [view.payload(this_device_id) for view in views],
        "lease": lease,
    }
