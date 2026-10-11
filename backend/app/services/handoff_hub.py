"""The open sockets, and the messages waiting for devices that have none.

In memory, on purpose: the server runs one worker (see the Dockerfile), so
there is exactly one of these, and a user's devices all meet in it. A device
on the socket gets its messages at once. A device that could not open the
socket (a proxy without WebSocket support, the Android playback service
with the app swiped away) polls, and its messages wait here for it, for a
little while.

Everything here is about delivery, never about the rules — those are in
`handoff`, which is synchronous and tested on its own. The hub holds no
database session; callers pass it the dicts to send.
"""

import asyncio
import time
from collections import defaultdict

from fastapi import WebSocket

# How long a message waits for a polling device before it is dropped. Longer
# than the slowest poll, shorter than a driver's patience.
PENDING_TTL_S = 45
# A runaway producer must not grow a list without bound for a device that
# never comes back; the oldest are dropped past this.
PENDING_LIMIT = 20
# A socket counts as live while its last pong (or its attach) is this recent.
# Two ping intervals and change: a phone the system suspended stops
# answering, and within this window it stops being "online" — a transfer to
# it is refused rather than lost into a socket nobody is reading.
LIVE_WINDOW_S = 25
# A single send may not stall the fan-out: a peer that has stopped reading
# fills its buffer and then blocks the writer, and every other device waits.
SEND_TIMEOUT_S = 5


class HandoffHub:
    def __init__(self) -> None:
        # user_id -> device_id -> socket. One socket per device; a second
        # connection for the same device (a reloaded tab) replaces the first.
        self._sockets: dict[int, dict[str, WebSocket]] = defaultdict(dict)
        # (user_id, device_id) -> [(enqueued_at, message)] for polling devices.
        self._pending: dict[tuple[int, str], list[tuple[float, dict]]] = defaultdict(list)
        # One lock per user, so fan-out for one account is ordered and two
        # users never wait on each other.
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        # (user_id, device_id) -> monotonic time of the last pong (or attach).
        self._last_pong: dict[tuple[int, str], float] = {}

    def lock(self, user_id: int) -> asyncio.Lock:
        return self._locks[user_id]

    def _prune_lock(self, user_id: int) -> None:
        """Forget a user's lock once nothing of theirs is here and nobody holds it."""
        lock = self._locks.get(user_id)
        if lock is not None and not lock.locked() and user_id not in self._sockets:
            del self._locks[user_id]

    # --- sockets --------------------------------------------------------------

    async def attach(self, user_id: int, device_id: str, socket: WebSocket) -> None:
        """Register a device's socket, displacing any older one it had."""
        previous = self._sockets[user_id].get(device_id)
        if previous is not None and previous is not socket:
            try:
                await previous.close(code=4000)
            except Exception:  # noqa: BLE001 — the old socket may already be gone
                pass
        self._sockets[user_id][device_id] = socket
        self._last_pong[(user_id, device_id)] = time.monotonic()

    def detach(self, user_id: int, device_id: str, socket: WebSocket) -> None:
        """Drop a device's socket, but only if it is still the one we hold."""
        if self._sockets.get(user_id, {}).get(device_id) is socket:
            del self._sockets[user_id][device_id]
            self._last_pong.pop((user_id, device_id), None)
            if not self._sockets[user_id]:
                del self._sockets[user_id]
                self._prune_lock(user_id)

    # --- liveness -------------------------------------------------------------

    def note_pong(self, user_id: int, device_id: str, now: float | None = None) -> None:
        if device_id in self._sockets.get(user_id, {}):
            self._last_pong[(user_id, device_id)] = time.monotonic() if now is None else now

    def silent_for(self, user_id: int, device_id: str, now: float | None = None) -> float:
        """Seconds since the device last answered; infinity if it has no socket."""
        at = self._last_pong.get((user_id, device_id))
        if at is None:
            return float("inf")
        return (time.monotonic() if now is None else now) - at

    def connected_device_ids(self, user_id: int, now: float | None = None) -> set[str]:
        """The devices with a socket that is answering pings.

        A socket that has gone quiet is still held — its handler closes it
        once the pings go unanswered — but it is not a device anyone can hand
        the music to, so it is not in this set.
        """
        now = time.monotonic() if now is None else now
        return {
            device_id
            for device_id in self._sockets.get(user_id, {})
            if now - self._last_pong.get((user_id, device_id), now) <= LIVE_WINDOW_S
        }

    def is_connected(self, user_id: int, device_id: str) -> bool:
        """Whether a socket is held for the device at all, answering or not."""
        return device_id in self._sockets.get(user_id, {})

    # --- delivery -------------------------------------------------------------

    async def send(self, user_id: int, device_id: str, message: dict) -> bool:
        """To one device: its socket if it has one, else the pending queue.

        Returns True if it went over a live socket. A failed send drops the
        socket and falls through to pending, so a command is not lost to a
        half-dead connection.
        """
        socket = self._sockets.get(user_id, {}).get(device_id)
        if socket is not None:
            if await self._send_to(user_id, device_id, socket, message):
                return True
        self._enqueue(user_id, device_id, message)
        return False

    async def _send_to(self, user_id: int, device_id: str, socket: WebSocket, message: dict) -> bool:
        """One send, bounded in time; a failure or a stall drops the socket."""
        try:
            await asyncio.wait_for(socket.send_json(message), timeout=SEND_TIMEOUT_S)
            return True
        except Exception:  # noqa: BLE001 — closed, errored, or not reading
            self.detach(user_id, device_id, socket)
            return False

    async def broadcast(self, user_id: int, message: dict, *, exclude: str | None = None) -> None:
        """To every socket of a user, at once; pending is for one-device sends only.

        A broadcast is a lease or a state change: a device that is only
        polling learns it on its next `GET /playback/devices`, which returns
        the lease, so it does not need the message held for it. The sends run
        together, each with its own deadline, so one device that has stopped
        reading cannot hold the others' news.
        """
        targets = [
            (device_id, socket)
            for device_id, socket in self._sockets.get(user_id, {}).items()
            if device_id != exclude
        ]
        if not targets:
            return
        await asyncio.gather(
            *(self._send_to(user_id, device_id, socket, message) for device_id, socket in targets),
            return_exceptions=True,
        )

    def _enqueue(self, user_id: int, device_id: str, message: dict, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        queue = self._pending[(user_id, device_id)]
        queue.append((now, message))
        if len(queue) > PENDING_LIMIT:
            del queue[: len(queue) - PENDING_LIMIT]
        self._sweep_pending(now)

    def _sweep_pending(self, now: float) -> None:
        """Forget the queues of devices that never came back for them."""
        gone = [
            key for key, queue in self._pending.items()
            if not queue or now - queue[-1][0] > PENDING_TTL_S
        ]
        for key in gone:
            del self._pending[key]

    def drain_pending(self, user_id: int, device_id: str, now: float | None = None) -> list[dict]:
        """The waiting messages for a polling device, freshest kept, expired dropped."""
        now = time.monotonic() if now is None else now
        key = (user_id, device_id)
        queue = self._pending.get(key)
        if not queue:
            return []
        alive = [message for (at, message) in queue if now - at <= PENDING_TTL_S]
        del self._pending[key]
        return alive


# The one hub (one worker, one process).
hub = HandoffHub()
