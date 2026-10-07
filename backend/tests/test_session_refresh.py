"""A session renews itself while it is being used.

The cookie was minted at sign-in and never again, so "stay signed in" ended a
week after sign-in however much the app was used. A request that arrives with
a session past half its life now goes back out with a fresh cookie.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.services.auth import (
    SESSION_REFRESH_AFTER_RATIO,
    decode_access_token,
    reissue_access_token,
    session_token_needs_refresh,
)
from tests.test_pass_p import _admin


def _token(**claims) -> str:
    payload = {"sub": "1", "username": "admin", "role": "admin", **claims}
    return jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def _expiring_in(minutes: float, **claims) -> str:
    return _token(
        exp=datetime.now(timezone.utc) + timedelta(minutes=minutes),
        **claims,
    )


def _session_cookie(response) -> str | None:
    """The value the response sets the session cookie to, or None if it sets none."""
    for key, value in response.headers.multi_items():
        if key.lower() == "set-cookie" and value.startswith(f"{settings.auth_cookie_name}="):
            return value
    return None


# --- the policy ----------------------------------------------------------------


def test_only_a_session_halfway_through_its_life_is_renewed():
    whole_life = settings.access_token_expire_minutes

    fresh = decode_access_token(_expiring_in(whole_life))
    assert session_token_needs_refresh(fresh) is False

    half_spent = decode_access_token(_expiring_in(whole_life * SESSION_REFRESH_AFTER_RATIO - 1))
    assert session_token_needs_refresh(half_spent) is True

    # Expired is a sign-in, not a renewal.
    assert session_token_needs_refresh(decode_access_token(_expiring_in(-1))) is False

    # Not sessions: a stream token (it travels in URLs), and one with no subject.
    stream = decode_access_token(_expiring_in(1, purpose="stream"))
    assert session_token_needs_refresh(stream) is False
    assert session_token_needs_refresh({"exp": 1, "username": "admin"}) is False
    assert session_token_needs_refresh(None) is False
    assert session_token_needs_refresh({"sub": "1"}) is False


def test_a_renewed_token_keeps_every_other_claim():
    original = decode_access_token(_expiring_in(1, pwd="abc123"))
    renewed = decode_access_token(reissue_access_token(original))

    assert {key: value for key, value in renewed.items() if key != "exp"} == {
        key: value for key, value in original.items() if key != "exp"
    }
    # The password fingerprint rides along, so a password changed elsewhere
    # still ends this session.
    assert renewed["pwd"] == "abc123"
    assert renewed["exp"] > original["exp"]


# --- over HTTP -----------------------------------------------------------------


@pytest.fixture
def signed_in(client):
    _admin(client)
    return client


def _aging_admin_token(db_session_factory) -> str:
    """A genuine admin session with less than half its life left."""
    from app.models.user import User
    from app.services.auth import password_fingerprint

    db = db_session_factory()
    try:
        admin = db.query(User).filter_by(username="admin").one()
        return _expiring_in(
            settings.access_token_expire_minutes * SESSION_REFRESH_AFTER_RATIO - 1,
            sub=str(admin.id),
            pwd=password_fingerprint(admin.password_hash),
        )
    finally:
        db.close()


def _session_cookies(response) -> list[str]:
    return [
        value
        for key, value in response.headers.multi_items()
        if key.lower() == "set-cookie" and value.startswith(f"{settings.auth_cookie_name}=")
    ]


@pytest.fixture
def only_cookie(client):
    """Send exactly one session cookie.

    The test client's jar is shared for the session, and a request carrying
    both its cookie and a hand-made one tests nothing: the two would disagree
    about which is being renewed.
    """
    # Read at the jar level: a cookie set by hand and one set by a response
    # are two entries under one name, which `dict(client.cookies)` refuses.
    held = [(c.name, c.value, c.domain, c.path) for c in client.cookies.jar]

    def send(token: str | None):
        client.cookies.clear()
        if token is not None:
            client.cookies.set(settings.auth_cookie_name, token)
        return client

    yield send

    client.cookies.clear()
    for name, value, domain, path in held:
        client.cookies.set(name, value, domain=domain, path=path)


def test_a_fresh_session_is_left_alone(signed_in):
    assert _session_cookie(signed_in.get("/api/auth/me")) is None


def test_a_session_past_half_its_life_comes_back_renewed(signed_in, only_cookie, db_session_factory):
    aging = _aging_admin_token(db_session_factory)

    response = only_cookie(aging).get("/api/auth/me")
    assert response.status_code == 200

    cookie = _session_cookie(response)
    assert cookie and f"Max-Age={settings.access_token_expire_minutes * 60}" in cookie
    assert "HttpOnly" in cookie and "Path=/" in cookie

    renewed = cookie.split("=", 1)[1].split(";", 1)[0]
    assert decode_access_token(renewed)["exp"] > decode_access_token(aging)["exp"]

    # And the renewed cookie is a working session.
    assert only_cookie(renewed).get("/api/auth/me").status_code == 200


def test_a_refused_session_is_not_renewed(only_cookie):
    # Signed by this server, past half its life, but for a user that is not
    # there: the answer is 401 and the cookie must not be re-dated.
    aging = _expiring_in(
        settings.access_token_expire_minutes * SESSION_REFRESH_AFTER_RATIO - 1,
        sub="999999",
    )

    response = only_cookie(aging).get("/api/auth/me")

    assert response.status_code == 401
    assert _session_cookie(response) is None


def test_a_route_that_sets_the_cookie_itself_decides(signed_in, only_cookie, db_session_factory):
    aging = _aging_admin_token(db_session_factory)

    # Signing out an aging session: the route clears the cookie, and the
    # renewal must not add a second one putting it back.
    cleared = _session_cookies(only_cookie(aging).post("/api/auth/logout"))
    assert len(cleared) == 1
    assert "Max-Age=0" in cleared[0]

    # Signing in with one still on the device: one cookie, the route's own.
    issued = _session_cookies(
        only_cookie(aging).post(
            "/api/auth/login",
            json={"username": "admin", "password": "test-password-1"},
        )
    )
    assert len(issued) == 1
    assert f"Max-Age={settings.access_token_expire_minutes * 60}" in issued[0]


def test_a_renewal_rides_along_with_a_304(signed_in, only_cookie, db_session_factory):
    # The phone's index requests are mostly 304s. They are proof of life too,
    # so the cookie has to travel with a body-less answer.
    aging = _aging_admin_token(db_session_factory)
    first = only_cookie(aging).get("/api/playlists")
    etag = first.headers["etag"]

    again = only_cookie(aging).get("/api/playlists", headers={"If-None-Match": etag})

    assert again.status_code == 304
    assert len(_session_cookies(again)) == 1


# --- what the client is told ---------------------------------------------------


def test_health_says_how_long_a_session_is(signed_in):
    from app.routes.health import session_days

    body = signed_in.get("/api/health").json()

    assert body["session_days"] == session_days()
    assert body["session_days"] == -(-settings.access_token_expire_minutes // (60 * 24))
    assert "session-days" in body["capabilities"]


def test_a_forced_password_change_answers_with_its_code(signed_in, db_session_factory):
    """The phone reads `code` off the body; the header stays for anything else.

    This 403 used to be a bare sentence, indistinguishable from any other
    refusal, and the phone treated it as a dead session.
    """
    from app.models.user import User

    db = db_session_factory()
    try:
        admin = db.query(User).filter_by(username="admin").one()
        admin.must_change_password = True
        admin.temp_password_issued_at = None
        db.commit()
    finally:
        db.close()

    try:
        refused = signed_in.get("/api/playlists")
        allowed = signed_in.get("/api/auth/me")
    finally:
        db = db_session_factory()
        try:
            admin = db.query(User).filter_by(username="admin").one()
            admin.must_change_password = False
            db.commit()
        finally:
            db.close()

    assert refused.status_code == 403
    assert refused.json() == {
        "detail": "Choose a password before using the app.",
        "code": "password_change_required",
    }
    assert refused.headers["x-adjacent-code"] == "password_change_required"
    # The account can still see itself, which is how it reaches the screen.
    assert allowed.status_code == 200
    assert allowed.json()["must_change_password"] is True
