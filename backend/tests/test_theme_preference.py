"""The look an account wears: a preference like the time zone, kept on the
server so every device the listener signs in on matches, checked against
the server's own list, and Adjacent until they say otherwise."""

from tests.test_pass_p import _admin


def test_an_account_wears_adjacent_until_it_says_otherwise(client):
    _admin(client)
    me = client.get("/api/auth/me").json()
    user = me.get("user", me)
    assert user["theme"] == "adjacent"
    assert user["theme_seasonal"] is False
    assert user["theme_southern"] is False


def test_a_theme_is_saved_and_the_time_zone_is_left_alone(client):
    _admin(client)
    assert client.patch("/api/auth/me/preferences", json={"timezone": "Europe/London"}).status_code == 200

    saved = client.patch("/api/auth/me/preferences", json={"theme": "halloween", "theme_seasonal": True})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["theme"] == "halloween"
    assert body["theme_seasonal"] is True
    assert body["theme_southern"] is False
    assert body["timezone"] == "Europe/London", "a theme save does not touch the time zone"

    me = client.get("/api/auth/me").json()
    user = me.get("user", me)
    assert user["theme"] == "halloween" and user["theme_seasonal"] is True

    south = client.patch("/api/auth/me/preferences", json={"theme_southern": True}).json()
    assert south["theme"] == "halloween" and south["theme_southern"] is True

    back = client.patch("/api/auth/me/preferences", json={"theme": None, "theme_seasonal": False, "theme_southern": False}).json()
    assert back["theme"] == "adjacent" and back["theme_seasonal"] is False and back["theme_southern"] is False
    client.patch("/api/auth/me/preferences", json={"timezone": None})


def test_only_the_servers_themes_are_accepted(client):
    _admin(client)
    assert client.patch("/api/auth/me/preferences", json={"theme": "green"}).status_code == 422
    assert client.patch("/api/auth/me/preferences", json={"theme": "Halloween"}).status_code == 422
    assert client.patch("/api/auth/me/preferences", json={"theme": "x" * 40}).status_code == 422
    health = client.get("/api/health").json()
    assert "themes" in health["capabilities"]
    assert health["api_version"] >= 13
