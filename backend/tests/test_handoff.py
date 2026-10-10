"""Device handoff: the lease rules, the socket, and the HTTP twins.

The rule is one device playing at a time, kept by the server. These cover the
service (synchronous, no socket), a socket round trip through Starlette's test
client, and the HTTP twins the polling clients use.
"""

from datetime import datetime, timedelta

import pytest

from tests.test_pass_p import _admin, _make_track


HELLO_A = {"type": "hello", "device_id": "dev-a", "name": "Phone A", "kind": "phone"}
HELLO_B = {"type": "hello", "device_id": "dev-b", "name": "Web B", "kind": "web"}


@pytest.fixture(autouse=True)
def _clean_handoff_rows(client, db_session_factory):
    """Leave the shared schema as we found it.

    The suite runs on one schema for the whole session, and the maintenance
    sweep counts every track with no file on disk. Our phantom `/h/` tracks
    would read as missing and inflate its count, so each test clears the rows
    it could have added — queue items first, then sessions, devices and the
    tracks themselves, which is also the order the foreign keys need on
    Postgres.
    """
    yield
    from app.models.playback_device import PlaybackDevice
    from app.models.playback_queue_item import PlaybackQueueItem
    from app.models.playback_session import PlaybackSession
    from app.models.track import Track

    db = db_session_factory()
    try:
        db.query(PlaybackQueueItem).delete(synchronize_session=False)
        db.query(PlaybackSession).delete(synchronize_session=False)
        db.query(PlaybackDevice).delete(synchronize_session=False)
        db.query(Track).filter(Track.file_path.like("/h/%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _state(track_id, ids, index=0, version=1, playing=True):
    return {
        "current_track_id": track_id,
        "queue_index": index,
        "current_time_seconds": 0,
        "is_playing": playing,
        "is_shuffle": False,
        "is_loop": False,
        "queue_track_ids": ids,
        "version": version,
    }


# --- the service, directly ---------------------------------------------------


@pytest.fixture
def svc(client, db_session_factory, request):
    """A fresh user id for the service-level tests.

    Depends on `client` so the whole app has imported — that is what registers
    every model on the metadata the session fixture builds the schema from.
    The username is unique per test, since the schema is shared across the run.
    """
    from app.models.user import User

    db = db_session_factory()
    try:
        user = User(username=f"handoff-{request.node.name[:40]}", password_hash="x", role="user")
        db.add(user)
        db.commit()
        uid = user.id
    finally:
        db.close()
    return uid


def test_a_claim_moves_the_lease(svc, db_session_factory):
    from app.services import handoff

    db = db_session_factory()
    try:
        a = handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        b = handoff.register(db, svc, {"device_id": "b", "name": "B", "kind": "web"})

        handoff.claim(db, svc, a, None)
        session = handoff.get_or_create_playback_session(db, svc)
        assert session.active_device_id == a.id

        handoff.claim(db, svc, b, None)
        db.refresh(session)
        assert session.active_device_id == b.id
    finally:
        db.close()


def test_a_report_from_a_non_holder_is_refused(svc, db_session_factory):
    from app.services import handoff
    from app.services.handoff import HandoffError

    db = db_session_factory()
    try:
        a = handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        b = handoff.register(db, svc, {"device_id": "b", "name": "B", "kind": "web"})
        handoff.claim(db, svc, a, None)

        with pytest.raises(HandoffError) as caught:
            handoff.report(db, svc, b, {"current_time_seconds": 5, "is_playing": True})
        assert caught.value.code == "device_not_active"
    finally:
        db.close()


def test_a_stale_version_is_ignored(svc, db_session_factory):
    from app.services import handoff

    db = db_session_factory()
    try:
        a = handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        handoff.claim(db, svc, a, None)
        session = handoff.get_or_create_playback_session(db, svc)

        assert handoff.apply_position(db, session, {"current_time_seconds": 30, "is_playing": True, "version": 5})
        assert session.current_time_seconds == 30
        # An older report does not wind the clock back.
        assert handoff.apply_position(db, session, {"current_time_seconds": 10, "is_playing": True, "version": 3}) is False
        db.refresh(session)
        assert session.current_time_seconds == 30
    finally:
        db.close()


def test_a_transfer_to_an_away_device_is_refused(svc, db_session_factory):
    from app.services import handoff
    from app.services.handoff import HandoffError

    db = db_session_factory()
    try:
        a = handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        b = handoff.register(db, svc, {"device_id": "b", "name": "B", "kind": "web"})
        # Make b look long gone.
        b.last_seen_at = datetime.utcnow() - timedelta(minutes=10)
        db.commit()
        handoff.claim(db, svc, a, None)

        with pytest.raises(HandoffError) as caught:
            handoff.transfer(db, svc, a, "b", None, connected=set())
        assert caught.value.code == "device_away"
    finally:
        db.close()


def test_a_silent_holder_loses_the_lease_to_the_next_claim(svc, db_session_factory):
    from app.services import handoff

    db = db_session_factory()
    try:
        a = handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        b = handoff.register(db, svc, {"device_id": "b", "name": "B", "kind": "web"})
        handoff.claim(db, svc, a, None)
        a.last_seen_at = datetime.utcnow() - timedelta(seconds=90)
        db.commit()

        session = handoff.get_or_create_playback_session(db, svc)
        # The holder is stale: no socket, last seen long ago.
        assert handoff.lease_payload(db, session, connected=set())["stale"] is True
        # Anyone may claim without ceremony.
        handoff.claim(db, svc, b, None)
        db.refresh(session)
        assert session.active_device_id == b.id
        assert handoff.lease_payload(db, session, connected={"b"})["stale"] is False
    finally:
        db.close()


def test_devices_are_listed_active_first_then_online(svc, db_session_factory):
    from app.services import handoff

    db = db_session_factory()
    try:
        handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        b = handoff.register(db, svc, {"device_id": "b", "name": "B", "kind": "web"})
        c = handoff.register(db, svc, {"device_id": "c", "name": "C", "kind": "tablet"})
        c.last_seen_at = datetime.utcnow() - timedelta(minutes=5)
        db.commit()
        handoff.claim(db, svc, b, None)

        views = handoff.list_devices(db, svc, connected={"a", "b"})
        order = [v.device_id for v in views]
        assert order[0] == "b"  # active first
        assert order[-1] == "c"  # away last
        assert next(v for v in views if v.device_id == "c").online is False
    finally:
        db.close()


# --- the legacy PUT still works ----------------------------------------------


def test_the_old_playback_put_without_a_device_header_still_works(client, db_session_factory):
    _admin(client)
    tid = _make_track(db_session_factory, "/h/legacy.flac")
    body = {
        "current_track_id": tid,
        "queue_index": 0,
        "current_time_seconds": 3,
        "is_playing": True,
        "is_shuffle": False,
        "is_loop": False,
        "queue_track_ids": [tid],
    }
    put = client.put("/api/playback", json=body)
    assert put.status_code == 200, put.text
    assert put.json()["current_track_id"] == tid


# --- the socket --------------------------------------------------------------


def test_two_sockets_see_each_others_claims(client, db_session_factory):
    _admin(client)
    tid = _make_track(db_session_factory, "/h/sock.flac")

    with client.websocket_connect("/api/playback/ws") as a, client.websocket_connect("/api/playback/ws") as b:
        a.send_json(HELLO_A)
        b.send_json(HELLO_B)
        # Each gets its devices snapshot first.
        assert a.receive_json()["type"] == "devices"
        assert b.receive_json()["type"] == "devices"

        a.send_json({"type": "claim", "state": _state(tid, [tid])})
        # B is told the lease moved to A.
        msg = _next_of(b, "lease")
        assert msg["active_device_id"] == "dev-a"

        # A command from B reaches A.
        b.send_json({"type": "command", "action": "pause", "args": {}})
        cmd = _next_of(a, "command")
        assert cmd["action"] == "pause"


def test_the_socket_refuses_a_bad_cookie(client):
    # No login: no session cookie, so the socket is closed before hello.
    client.cookies.clear()
    with pytest.raises(Exception):
        with client.websocket_connect("/api/playback/ws") as ws:
            ws.receive_json()


def _next_of(ws, wanted, limit=6):
    """The next frame of a wanted type, skipping pings and the devices snapshot."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == wanted:
            return msg
    raise AssertionError(f"no {wanted} frame within {limit} messages")


# --- the HTTP twins ----------------------------------------------------------


def test_the_http_twins_carry_the_rule(client, db_session_factory):
    _admin(client)
    tid = _make_track(db_session_factory, "/h/twin.flac")

    # Two devices say hello over HTTP.
    client.post("/api/playback/devices/hello", json={"device_id": "t-a", "name": "A", "kind": "phone"})
    client.post("/api/playback/devices/hello", json={"device_id": "t-b", "name": "B", "kind": "web"})

    # A claims.
    claim = client.post(
        "/api/playback/claim",
        json={"state": _state(tid, [tid])},
        headers={"X-Adjacent-Device": "t-a"},
    )
    assert claim.status_code == 200, claim.text

    # B sees A active.
    devices = client.get("/api/playback/devices", headers={"X-Adjacent-Device": "t-b"}).json()
    assert devices["lease"]["active_device_id"] == "t-a"
    active = next(d for d in devices["devices"] if d["device_id"] == "t-a")
    assert active["is_active"] is True

    # B reporting is refused: it does not hold the lease.
    refused = client.post(
        "/api/playback/state",
        json={"current_time_seconds": 9, "is_playing": True},
        headers={"X-Adjacent-Device": "t-b"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "device_not_active"

    # A command from B for A waits for A, which is only polling.
    client.post(
        "/api/playback/command",
        json={"action": "pause", "args": {}},
        headers={"X-Adjacent-Device": "t-b"},
    )
    polled = client.get("/api/playback/devices", headers={"X-Adjacent-Device": "t-a"}).json()
    assert any(c["action"] == "pause" for c in polled.get("pending_commands", []))


def test_a_claim_without_a_device_header_is_a_400(client, db_session_factory):
    _admin(client)
    tid = _make_track(db_session_factory, "/h/nohdr.flac")
    resp = client.post("/api/playback/claim", json={"state": _state(tid, [tid])})
    assert resp.status_code == 400


# --- health ------------------------------------------------------------------


def test_health_advertises_handoff(client):
    body = client.get("/api/health").json()
    assert body["api_version"] >= 8
    assert "device-handoff" in body["capabilities"]
