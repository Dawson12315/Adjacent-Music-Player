"""The per-address login limiter slows wrong guesses, never a right password.

Behind a proxy that is not trusted to say who the client is, every client
shares one address; the limiter used to be checked before the password, so
ten wrong guesses by anyone locked the account's owner out too.
"""

from app.services.rate_limit import login_limiter, username_login_limiter
from tests.test_pass_p import _admin


def test_the_right_password_gets_in_after_others_guessed_wrong(client):
    _admin(client)
    client.cookies.clear()

    # Twelve wrong guesses at the admin's name from this address: past both
    # tiers' limits, and the last ones answer 429.
    last = None
    for _ in range(12):
        last = client.post("/api/auth/login", json={"username": "admin", "password": "definitely-wrong"})
    assert last.status_code == 429
    assert last.headers.get("retry-after")

    # The right password still gets in.
    good = client.post("/api/auth/login", json={"username": "admin", "password": "test-password-1"})
    assert good.status_code == 200, good.text

    login_limiter.record_success("testclient:admin")
    username_login_limiter.record_success("admin")
