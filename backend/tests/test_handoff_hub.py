"""The hub's liveness and housekeeping, with fake sockets and a fake clock."""

import asyncio

import pytest

from app.services.handoff_hub import LIVE_WINDOW_S, PENDING_TTL_S, HandoffHub


class FakeSocket:
    def __init__(self, *, stall: bool = False):
        self.sent = []
        self.closed = None
        self.stall = stall

    async def send_json(self, message):
        if self.stall:
            await asyncio.sleep(3600)
        self.sent.append(message)

    async def close(self, code=1000):
        self.closed = code


def test_a_socket_that_stops_answering_pings_is_no_longer_connected():
    hub = HandoffHub()
    sock = FakeSocket()
    asyncio.run(hub.attach(1, "phone", sock))
    assert "phone" in hub.connected_device_ids(1)

    # Quiet past the window: still held, no longer offered.
    hub._last_pong[(1, "phone")] -= LIVE_WINDOW_S + 1
    assert "phone" not in hub.connected_device_ids(1)
    assert hub.is_connected(1, "phone") is True
    assert hub.silent_for(1, "phone") > LIVE_WINDOW_S

    # A pong brings it back.
    hub.note_pong(1, "phone")
    assert "phone" in hub.connected_device_ids(1)


def test_a_pong_from_a_device_without_a_socket_is_ignored():
    hub = HandoffHub()
    hub.note_pong(1, "ghost")
    assert hub.silent_for(1, "ghost") == float("inf")


def test_detach_forgets_the_pong_and_the_idle_lock():
    hub = HandoffHub()
    sock = FakeSocket()
    asyncio.run(hub.attach(1, "phone", sock))
    hub.lock(1)
    hub.detach(1, "phone", sock)
    assert (1, "phone") not in hub._last_pong
    assert 1 not in hub._locks


def test_a_stalled_peer_does_not_hold_the_broadcast():
    hub = HandoffHub()
    good = FakeSocket()
    stuck = FakeSocket(stall=True)

    async def run():
        await hub.attach(1, "good", good)
        await hub.attach(1, "stuck", stuck)
        from app.services import handoff_hub

        handoff_hub.SEND_TIMEOUT_S = 0.05
        try:
            await asyncio.wait_for(hub.broadcast(1, {"type": "lease"}), timeout=2)
        finally:
            handoff_hub.SEND_TIMEOUT_S = 5

    asyncio.run(run())
    assert good.sent == [{"type": "lease"}]
    # The stalled socket was dropped; the good one stays.
    assert hub.is_connected(1, "stuck") is False
    assert hub.is_connected(1, "good") is True


def test_pending_queues_of_devices_that_never_came_back_are_swept():
    hub = HandoffHub()
    hub._enqueue(1, "a", {"type": "command"}, now=0.0)
    hub._enqueue(1, "b", {"type": "command"}, now=PENDING_TTL_S + 10)
    # Enqueuing for b swept a, whose newest message had expired.
    assert (1, "a") not in hub._pending
    assert (1, "b") in hub._pending
    assert hub.drain_pending(1, "b", now=PENDING_TTL_S + 11) == [{"type": "command"}]
    assert (1, "b") not in hub._pending


@pytest.mark.parametrize("exclude", [None, "a"])
def test_broadcast_reaches_every_socket_but_the_excluded(exclude):
    hub = HandoffHub()
    a, b = FakeSocket(), FakeSocket()

    async def run():
        await hub.attach(1, "a", a)
        await hub.attach(1, "b", b)
        await hub.broadcast(1, {"type": "lease"}, exclude=exclude)

    asyncio.run(run())
    assert b.sent == [{"type": "lease"}]
    assert a.sent == ([] if exclude == "a" else [{"type": "lease"}])
