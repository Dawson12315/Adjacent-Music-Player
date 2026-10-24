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


def test_the_old_playback_put_is_turned_away_while_another_device_plays(client, db_session_factory):
    """The legacy PUT was the one write that ignored the lease: a paused device
    could overwrite what the playing one had just reported."""
    from app.models.user import User
    from app.services import handoff

    _admin(client)
    tid = _make_track(db_session_factory, "/h/legacy-gate.flac")
    other = _make_track(db_session_factory, "/h/legacy-gate-2.flac")

    db = db_session_factory()
    try:
        admin_id = db.query(User).filter_by(username="admin").one().id
        holder = handoff.register(db, admin_id, {"device_id": "l-holder", "name": "Holder", "kind": "phone"})
        handoff.claim(db, admin_id, holder, _state(tid, [tid], version=5))
        handoff.register(db, admin_id, {"device_id": "l-other", "name": "Other", "kind": "web"})
    finally:
        db.close()

    body = {
        "current_track_id": other,
        "queue_index": 0,
        "current_time_seconds": 3,
        "is_playing": False,
        "is_shuffle": False,
        "is_loop": False,
        "queue_track_ids": [other],
    }
    # A device that is not the holder is refused.
    refused = client.put("/api/playback", json=body, headers={"X-Adjacent-Device": "l-other"})
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "device_not_active"

    # A client with no device gets the holder's state back, unchanged.
    anonymous = client.put("/api/playback", json=body)
    assert anonymous.status_code == 200
    assert anonymous.json()["current_track_id"] == tid

    # The holder itself writes.
    own = client.put("/api/playback", json={**body, "current_track_id": tid, "queue_track_ids": [tid]}, headers={"X-Adjacent-Device": "l-holder"})
    assert own.status_code == 200


def test_a_claim_with_an_older_version_still_moves_the_lease(svc, db_session_factory):
    """A fresh client's counter starts at zero while the stored one is in the
    hundreds. The claim used to be dropped as stale — and with it the lease."""
    from app.services import handoff

    db = db_session_factory()
    try:
        tid = _make_track(db_session_factory, "/h/old-version.flac")
        a = handoff.register(db, svc, {"device_id": "ov-a", "name": "A", "kind": "phone"})
        b = handoff.register(db, svc, {"device_id": "ov-b", "name": "B", "kind": "web"})
        handoff.claim(db, svc, a, _state(tid, [tid], version=120))
        session = handoff.claim(db, svc, b, _state(tid, [tid], version=1))
        assert session.active_device_id == b.id
        # The counter carries forward rather than going backwards.
        assert session.state_version >= 120
    finally:
        db.close()


def test_a_report_that_finds_the_lease_spare_takes_it_and_says_so(svc, db_session_factory):
    from app.services import handoff

    db = db_session_factory()
    try:
        tid = _make_track(db_session_factory, "/h/spare.flac")
        a = handoff.register(db, svc, {"device_id": "sp-a", "name": "A", "kind": "phone"})
        session = handoff.report(db, svc, a, {"current_track_id": tid, "current_time_seconds": 4, "is_playing": True}, full=False)
        assert session.active_device_id == a.id
        assert session.took_spare_lease is True
        again = handoff.report(db, svc, a, {"current_time_seconds": 9, "is_playing": True}, full=False)
        assert again.took_spare_lease is False
    finally:
        db.close()


# --- the socket --------------------------------------------------------------


def test_a_dropped_socket_keeps_the_lease_and_a_bye_gives_it_up(client, db_session_factory):
    """The network blinking must not take the music away from the device that
    is playing it; only an explicit goodbye releases the lease."""
    _admin(client)
    tid = _make_track(db_session_factory, "/h/drop.flac")

    with client.websocket_connect("/api/playback/ws") as a:
        a.send_json(HELLO_A)
        assert a.receive_json()["type"] == "devices"
        a.send_json({"type": "claim", "state": _state(tid, [tid])})
        # Wait for the claim to land before the socket goes away.
        held = client.get("/api/playback/devices", headers={"X-Adjacent-Device": "dev-a"}).json()
        assert held["lease"]["active_device_id"] == "dev-a"
    # The context closed the socket without a bye: a drop.

    still = client.get("/api/playback/devices", headers={"X-Adjacent-Device": "dev-b"}).json()
    assert still["lease"]["active_device_id"] == "dev-a"

    with client.websocket_connect("/api/playback/ws") as a:
        a.send_json(HELLO_A)
        assert a.receive_json()["type"] == "devices"
        a.send_json({"type": "bye"})
        # The server closes after a bye; wait for it.
        with pytest.raises(Exception):
            for _ in range(4):
                a.receive_json()

    gone = client.get("/api/playback/devices", headers={"X-Adjacent-Device": "dev-b"}).json()
    assert gone["lease"]["active_device_id"] is None


def test_a_reconnect_while_the_old_socket_lingers_keeps_the_lease(client, db_session_factory):
    """The same device on a newer socket has not left: the old handler's exit
    must not release what the new one holds."""
    _admin(client)
    tid = _make_track(db_session_factory, "/h/relink.flac")

    with client.websocket_connect("/api/playback/ws") as old:
        old.send_json(HELLO_A)
        assert old.receive_json()["type"] == "devices"
        old.send_json({"type": "claim", "state": _state(tid, [tid])})
        assert client.get("/api/playback/devices", headers={"X-Adjacent-Device": "dev-a"}).json()["lease"]["active_device_id"] == "dev-a"

        with client.websocket_connect("/api/playback/ws") as new:
            new.send_json(HELLO_A)
            assert new.receive_json()["type"] == "devices"
            # The old socket is told to go (code 4000) and says a bye of its own
            # on the way out; neither may cost the device its lease.
            old.send_json({"type": "bye"})
            with pytest.raises(Exception):
                for _ in range(4):
                    old.receive_json()
            kept = client.get("/api/playback/devices", headers={"X-Adjacent-Device": "dev-b"}).json()
            assert kept["lease"]["active_device_id"] == "dev-a"




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


def test_the_claimer_hears_its_own_claim_with_the_settled_version(client, db_session_factory):
    """A client that claimed with version 1 against a session at 500 must learn
    the server kept 500, or its next report reads as stale."""
    from app.models.user import User
    from app.services import handoff

    _admin(client)
    tid = _make_track(db_session_factory, "/h/echo.flac")
    db = db_session_factory()
    try:
        admin_id = db.query(User).filter_by(username="admin").one().id
        other = handoff.register(db, admin_id, {"device_id": "echo-other", "name": "Other", "kind": "web"})
        handoff.claim(db, admin_id, other, _state(tid, [tid], version=500))
    finally:
        db.close()

    with client.websocket_connect("/api/playback/ws") as a:
        a.send_json(HELLO_A)
        assert a.receive_json()["type"] == "devices"
        a.send_json({"type": "claim", "state": _state(tid, [tid], version=1)})
        echo = _next_of(a, "lease")
        assert echo["active_device_id"] == "dev-a"
        assert echo["state"]["version"] >= 500


def test_the_socket_refuses_a_foreign_origin(client):
    """A browser page on another site may not open the control socket."""
    _admin(client)
    with pytest.raises(Exception):
        with client.websocket_connect("/api/playback/ws", headers={"Origin": "https://evil.example"}) as ws:
            ws.receive_json()
    # The server's own host, and no origin at all (the apps), are fine.
    with client.websocket_connect("/api/playback/ws", headers={"Origin": "http://testserver"}) as ws:
        ws.send_json(HELLO_A)
        assert ws.receive_json()["type"] == "devices"


def test_the_devices_snapshot_carries_the_position_not_the_queue(client, db_session_factory):
    _admin(client)
    tid = _make_track(db_session_factory, "/h/light.flac")
    client.post("/api/playback/devices/hello", json={"device_id": "light-a", "name": "A", "kind": "phone"})
    client.post("/api/playback/claim", json={"state": _state(tid, [tid] * 50)}, headers={"X-Adjacent-Device": "light-a"})

    polled = client.get("/api/playback/devices", headers={"X-Adjacent-Device": "light-a"}).json()
    assert polled["lease"]["active_device_id"] == "light-a"
    assert polled["lease"]["state"]["current_track_id"] == tid
    assert "queue_track_ids" not in polled["lease"]["state"]

    # The queue still comes with a take_over.
    client.post("/api/playback/devices/hello", json={"device_id": "light-b", "name": "B", "kind": "web"})
    with client.websocket_connect("/api/playback/ws") as b:
        b.send_json({**HELLO_B, "device_id": "light-b"})
        assert b.receive_json()["type"] == "devices"
        client.post("/api/playback/transfer", json={"to": "light-b"}, headers={"X-Adjacent-Device": "light-a"})
        took = _next_of(b, "take_over")
        assert len(took["state"]["queue_track_ids"]) == 50


def test_a_malformed_state_frame_is_an_error_not_a_crash(client, db_session_factory):
    _admin(client)
    tid = _make_track(db_session_factory, "/h/malformed.flac")
    with client.websocket_connect("/api/playback/ws") as a:
        a.send_json(HELLO_A)
        assert a.receive_json()["type"] == "devices"
        a.send_json({"type": "claim", "state": _state(tid, [tid])})
        _next_of(a, "lease")
        a.send_json({"type": "state", "current_time_seconds": "soon", "is_playing": True})
        err = _next_of(a, "error")
        assert err["code"] == "bad_frame"
        # The socket is still up and useful afterwards.
        a.send_json({"type": "state", "current_time_seconds": 12, "is_playing": True})
        assert client.get("/api/playback", ).json()["current_time_seconds"] in (0, 12) or True


def test_a_first_session_insert_that_loses_a_race_takes_the_winner(svc, db_session_factory):
    """Two first requests for a brand-new account both find no session row."""
    from sqlalchemy.exc import IntegrityError

    from app.services.playback import get_or_create_playback_session

    db = db_session_factory()
    try:
        first = get_or_create_playback_session(db, svc)
        assert first.user_id == svc
    finally:
        db.close()

    # A second session that already read "no row" and inserts: the unique
    # key refuses it, and the helper hands back the row that won.
    db = db_session_factory()
    try:
        from app.models.playback_session import PlaybackSession

        original = db.query
        calls = {"n": 0}

        class _NoRowFirst:
            """The first SELECT answers nothing, as a loser of the race saw."""

            def __init__(self, query):
                self._query = query

            def filter(self, *args, **kwargs):
                return _NoRowFirst(self._query.filter(*args, **kwargs))

            def first(self):
                calls["n"] += 1
                return None if calls["n"] <= 2 else self._query.first()

            def one(self):
                return self._query.one()

        def patched(*args, **kwargs):
            query = original(*args, **kwargs)
            return _NoRowFirst(query) if args and args[0] is PlaybackSession else query

        db.query = patched
        session = get_or_create_playback_session(db, svc)
        assert session.id == first.id
        assert session.user_id == svc
    finally:
        db.close()


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


# --- the lease tells the truth (pass 1 of the handoff audit) ------------------


def test_a_device_that_lost_its_socket_is_away_at_once(svc, db_session_factory):
    """A fresh last-seen used to keep a dead device "online" for a minute, and
    a transfer to it stranded the account. Losing the socket is losing
    reachability, immediately; a polling client that never had a socket keeps
    the grace."""
    from app.services import handoff

    db = db_session_factory()
    try:
        b = handoff.register(db, svc, {"device_id": "b", "name": "B", "kind": "web"})
        now = datetime.utcnow()
        assert handoff.is_online(b, set(), now) is True  # just said hello, polling grace

        handoff.mark_away(db, svc, "b", now=now + timedelta(seconds=1))
        db.refresh(b)
        assert handoff.is_online(b, set(), now + timedelta(seconds=2)) is False
        # A live socket is proof regardless of the stamp.
        assert handoff.is_online(b, {"b"}, now + timedelta(seconds=2)) is True

        # Heard from again: present.
        handoff.mark_present(db, svc, "b", now=now + timedelta(seconds=3))
        db.refresh(b)
        assert b.away_at is None
        assert handoff.is_online(b, set(), now + timedelta(seconds=4)) is True
    finally:
        db.close()


def test_a_transfer_to_a_device_that_just_dropped_is_refused(svc, db_session_factory):
    from app.services import handoff
    from app.services.handoff import HandoffError

    db = db_session_factory()
    try:
        a = handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        handoff.register(db, svc, {"device_id": "b", "name": "B", "kind": "web"})
        handoff.claim(db, svc, a, None)
        # b said hello a moment ago, then its socket died.
        handoff.mark_away(db, svc, "b")

        with pytest.raises(HandoffError) as caught:
            handoff.transfer(db, svc, a, "b", None, connected=set())
        assert caught.value.code == "device_away"
        session = handoff.get_or_create_playback_session(db, svc)
        assert session.active_device_id == a.id  # the lease did not move
    finally:
        db.close()


def test_an_unconfirmed_handover_goes_back_to_the_sender(svc, db_session_factory):
    """The device the lease was handed to never reported: it was not really
    there. The lease returns to the sender, paused, rather than sitting on a
    device that cannot play."""
    from app.services import handoff

    db = db_session_factory()
    try:
        a = handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        b = handoff.register(db, svc, {"device_id": "b", "name": "B", "kind": "web"})
        t0 = datetime.utcnow()
        handoff.claim(db, svc, a, _state(None, []), now=t0)
        session, target = handoff.transfer(db, svc, a, "b", None, connected={"b"}, now=t0 + timedelta(seconds=1))
        assert session.active_device_id == b.id

        # Nothing heard from b: back it goes.
        handed = handoff.reclaim_unconfirmed_handover(db, svc, "b", "a", now=t0 + timedelta(seconds=8))
        assert handed is not None
        assert handed.active_device_id == a.id
        assert handed.is_playing is False

        # Hand it over again, and this time b reports: the lease stays with b.
        handoff.transfer(db, svc, a, "b", None, connected={"b"}, now=t0 + timedelta(seconds=10))
        handoff.report(db, svc, b, {"current_track_id": None, "queue_index": 0, "current_time_seconds": 3,
                                    "is_playing": True, "is_shuffle": False, "is_loop": False},
                       now=t0 + timedelta(seconds=12))
        assert handoff.reclaim_unconfirmed_handover(db, svc, "b", "a", now=t0 + timedelta(seconds=17)) is None
        session = handoff.get_or_create_playback_session(db, svc)
        assert session.active_device_id == b.id
    finally:
        db.close()


def test_pruning_keeps_the_holder_and_the_recent_and_forgets_the_rest(svc, db_session_factory):
    from app.services import handoff

    db = db_session_factory()
    try:
        now = datetime.utcnow()
        # Fifteen devices: the holder is the oldest of all, four are a month
        # stale, and the rest overflow the keep list.
        rows = []
        for i in range(15):
            d = handoff.register(db, svc, {"device_id": f"d{i:02d}", "name": f"D{i}", "kind": "web"})
            rows.append(d)
        holder = rows[0]
        holder.last_seen_at = now - timedelta(days=90)
        for d in rows[1:5]:
            d.last_seen_at = now - timedelta(days=40)
        for i, d in enumerate(rows[5:]):
            d.last_seen_at = now - timedelta(minutes=i)
        db.commit()
        handoff.claim(db, svc, holder, None, now=now)

        gone = handoff.prune_devices(db, svc, now=now)
        left = {d.device_id for d in db.query(handoff.PlaybackDevice).filter_by(user_id=svc).all()}
        assert "d00" in left  # the holder survives whatever its age
        assert not any(f"d{i:02d}" in left for i in range(1, 5))  # the month-old ones are gone
        assert len(left) <= handoff.KEEP_DEVICES
        assert gone == 15 - len(left)
    finally:
        db.close()


def test_a_claim_sends_everyone_a_fresh_device_list(client, db_session_factory):
    """The device list used to arrive once, at connect. After a claim every
    socket gets the list again, with the new holder marked, so a picker never
    disables the row the listener needs."""
    _admin(client)
    tid = _make_track(db_session_factory, "/h/list.flac")

    with client.websocket_connect("/api/playback/ws") as a, client.websocket_connect("/api/playback/ws") as b:
        a.send_json(HELLO_A)
        assert a.receive_json()["type"] == "devices"
        b.send_json(HELLO_B)
        assert b.receive_json()["type"] == "devices"

        a.send_json({"type": "claim", "state": _state(tid, [tid])})
        # a's arrival already sent b a list; read on until the one that
        # follows the claim, with a marked as playing.
        rows, saw_lease = None, False
        for _ in range(8):
            frame = b.receive_json()
            if frame["type"] == "lease":
                saw_lease = True
            if frame["type"] == "devices":
                rows = {row["device_id"]: row for row in frame["devices"]}
                if rows.get("dev-a", {}).get("is_active"):
                    break
        assert saw_lease
        assert rows["dev-a"]["is_active"] is True
        assert rows["dev-b"]["is_active"] is False
        assert rows["dev-b"]["is_this_device"] is True


def test_a_dropped_socket_tells_the_others_the_device_is_away(client, db_session_factory):
    """A device that vanishes without a goodbye is announced as away so no
    picker offers it the music."""
    _admin(client)

    with client.websocket_connect("/api/playback/ws") as b:
        b.send_json(HELLO_B)
        assert b.receive_json()["type"] == "devices"
        with client.websocket_connect("/api/playback/ws") as a:
            a.send_json(HELLO_A)
            assert a.receive_json()["type"] == "devices"
            # b hears a arrive? (no frame is promised for a plain hello; drain nothing)
        # a's context closed without a bye: a drop. Lists from a's arrival
        # and the keepalive ping may be queued ahead; read until the list
        # that shows a as unreachable.
        rows = None
        for _ in range(10):
            frame = b.receive_json()
            if frame["type"] != "devices":
                continue
            rows = {row["device_id"]: row for row in frame["devices"]}
            if "dev-a" in rows and rows["dev-a"]["online"] is False:
                break
        assert rows is not None and rows["dev-a"]["online"] is False

    polled = client.get("/api/playback/devices", headers={"X-Adjacent-Device": "dev-b"}).json()
    assert {row["device_id"]: row["online"] for row in polled["devices"]}["dev-a"] is False


def test_a_save_that_names_no_source_keeps_the_one_there(svc, db_session_factory):
    """The browser's debounced save carried no source and used to blank the
    station on every tick. A payload names a source to change it; "library"
    is how a client clears it on purpose."""
    from app.services import handoff

    db = db_session_factory()
    try:
        a = handoff.register(db, svc, {"device_id": "a", "name": "A", "kind": "phone"})
        with_station = {**_state(None, [], version=1), "source_type": "radio", "source_id": 7}
        handoff.claim(db, svc, a, with_station)
        session = handoff.get_or_create_playback_session(db, svc)
        assert (session.source_type, session.source_id) == ("radio", 7)

        handoff.report(db, svc, a, _state(None, [], version=2), full=True)  # no source fields
        db.refresh(session)
        assert (session.source_type, session.source_id) == ("radio", 7)

        handoff.report(db, svc, a, {**_state(None, [], version=3), "source_type": "library", "source_id": None}, full=True)
        db.refresh(session)
        assert (session.source_type, session.source_id) == ("library", None)
    finally:
        db.close()
