"""The hard one-device rule: the server refuses a stream to a device that does
not hold the lease while another device is playing.

Fail open is the whole safety story here, so most of these prove the gate says
*yes* — the music must never be refused to the device meant to play it.
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from tests.test_pass_p import _admin, _make_track


@pytest.fixture
def leaseuser(client, db_session_factory, request):
    from app.models.user import User

    db = db_session_factory()
    try:
        user = User(username=f"lease-{request.node.name[:40]}", password_hash="x", role="user")
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean(client, db_session_factory):
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
        db.query(Track).filter(Track.file_path.like("/lease/%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _hold(db, user_id, holder_device_id, *, playing, reported_ago_s):
    """Make holder_device_id the lease holder with a given playing state/age."""
    from app.services import handoff

    device = handoff.register(db, user_id, {"device_id": holder_device_id, "name": "Holder", "kind": "web"})
    session = handoff.get_or_create_playback_session(db, user_id)
    session.active_device_id = device.id
    session.is_playing = playing
    session.reported_at = datetime.utcnow() - timedelta(seconds=reported_ago_s)
    db.commit()
    return session


# --- the service, directly ----------------------------------------------------


def test_no_device_id_always_streams(leaseuser, db_session_factory):
    from app.services.handoff import stream_allowed

    db = db_session_factory()
    try:
        _hold(db, leaseuser, "holder", playing=True, reported_ago_s=1)
        assert stream_allowed(db, leaseuser, None) is True
        assert stream_allowed(db, leaseuser, "") is True
    finally:
        db.close()


def test_the_holder_always_streams(leaseuser, db_session_factory):
    from app.services.handoff import stream_allowed

    db = db_session_factory()
    try:
        _hold(db, leaseuser, "holder", playing=True, reported_ago_s=1)
        assert stream_allowed(db, leaseuser, "holder") is True
    finally:
        db.close()


def test_a_non_holder_is_refused_while_the_holder_plays(leaseuser, db_session_factory):
    from app.services.handoff import stream_allowed

    db = db_session_factory()
    try:
        _hold(db, leaseuser, "holder", playing=True, reported_ago_s=2)
        assert stream_allowed(db, leaseuser, "other") is False
    finally:
        db.close()


def test_a_non_holder_streams_when_the_holder_is_paused(leaseuser, db_session_factory):
    from app.services.handoff import stream_allowed

    db = db_session_factory()
    try:
        _hold(db, leaseuser, "holder", playing=False, reported_ago_s=2)
        assert stream_allowed(db, leaseuser, "other") is True
    finally:
        db.close()


def test_a_stale_holder_stops_blocking(leaseuser, db_session_factory):
    from app.services.handoff import stream_allowed

    db = db_session_factory()
    try:
        _hold(db, leaseuser, "holder", playing=True, reported_ago_s=30)
        assert stream_allowed(db, leaseuser, "other") is True
    finally:
        db.close()


def test_no_session_streams(leaseuser, db_session_factory):
    from app.services.handoff import stream_allowed

    db = db_session_factory()
    try:
        assert stream_allowed(db, leaseuser, "anyone") is True
    finally:
        db.close()


# --- over HTTP ----------------------------------------------------------------


def test_the_stream_route_refuses_a_non_holder(client, db_session_factory):
    _admin(client)
    tid = _make_track(db_session_factory, "/lease/a.flac")

    # Admin's own browser holds the lease and is playing.
    from app.models.user import User
    from app.services import handoff

    db = db_session_factory()
    try:
        admin_id = db.query(User).filter_by(username="admin").one().id
        _hold(db, admin_id, "holder-web", playing=True, reported_ago_s=1)
    finally:
        db.close()

    # A different device asking to stream is refused before it ever reaches the file.
    blocked = client.get(f"/api/tracks/{tid}/stream", headers={"X-Adjacent-Device": "other-phone"})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "device_not_active"

    # The holder is served (it fails later on the missing file, not the gate).
    holder = client.get(f"/api/tracks/{tid}/stream", headers={"X-Adjacent-Device": "holder-web"})
    assert holder.status_code != 409

    # A download is exempt even from another device.
    download = client.get(
        f"/api/tracks/{tid}/stream",
        headers={"X-Adjacent-Device": "other-phone", "X-Adjacent-Purpose": "download"},
    )
    assert download.status_code != 409

    # An old client with no device header passes the gate.
    old = client.get(f"/api/tracks/{tid}/stream")
    assert old.status_code != 409


def test_the_stream_route_serves_the_holder_a_real_file(client, db_session_factory):
    _admin(client)
    tmp = tempfile.NamedTemporaryFile(prefix="lease-", suffix=".mp3", delete=False)
    tmp.write(b"audio-bytes")
    tmp.close()
    tid = _make_track(db_session_factory, tmp.name)

    from app.models.user import User

    db = db_session_factory()
    try:
        admin_id = db.query(User).filter_by(username="admin").one().id
        _hold(db, admin_id, "holder-web", playing=True, reported_ago_s=1)
    finally:
        db.close()

    served = client.get(f"/api/tracks/{tid}/stream", headers={"X-Adjacent-Device": "holder-web"})
    assert served.status_code == 200
    os.unlink(tmp.name)

    # The track's file lives outside /lease/, so the autouse sweep would miss
    # it; remove it here to leave the shared schema as we found it.
    from app.models.track import Track

    db = db_session_factory()
    try:
        db.query(Track).filter(Track.id == tid).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_health_advertises_stream_lease(client):
    body = client.get("/api/health").json()
    assert body["api_version"] >= 9
    assert "stream-lease" in body["capabilities"]
