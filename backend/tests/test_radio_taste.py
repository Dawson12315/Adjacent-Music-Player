"""Pass 03: the thumbs steer the station now and leave a bounded correction on
the account that outlives the station, with a visible reset."""
from datetime import datetime, timedelta

import numpy as np

from tests.test_pass_p import _make_track
from tests.test_radio import ARTIST, GENRE, _artists, _next, _station, radio_library  # noqa: F401 — the module-scoped fixture
from tests.test_track_numbers_and_dismissals import _credit


def _build_map(db_session_factory):
    from app.services.recommendations import vector_map

    db = db_session_factory()
    try:
        vector_map.rebuild_vector_map(db)
        return vector_map.get_vector_index(db)
    finally:
        db.close()


def test_a_station_leans_toward_what_was_thumbed_up_and_away_from_what_was_thumbed_down(db_session_factory, radio_library):
    from app.services import radio_taste

    index = _build_map(db_session_factory)
    seed = radio_library["lp"][0]
    liked = radio_library["elsewhere"][0]
    plain = index.query_from([seed])
    leaned = radio_taste.station_query(index, [seed], more_ids=[liked])
    assert index.fit([liked], leaned)[liked] > index.fit([liked], plain)[liked]
    pushed = radio_taste.station_query(index, [seed], less_artist_keys=["elsewhere act"])
    assert index.fit([liked], pushed)[liked] < index.fit([liked], plain)[liked]


def test_a_vote_nudges_the_artist_a_bounded_decaying_step(client, db_session_factory, radio_library):
    from app.models.listener_artist_correction import ListenerArtistCorrection
    from app.services import radio_taste

    index = _build_map(db_session_factory)
    user_id = radio_library["user_id"]
    context = index.query_from([radio_library["lp"][0]])
    db = db_session_factory()
    try:
        radio_taste.reset(db, user_id)
        for _ in range(6):
            radio_taste.record_vote(db, index, user_id, "elsewhere act", "Elsewhere Act", context, up=True)
        row = db.query(ListenerArtistCorrection).filter_by(user_id=user_id, artist_key="elsewhere act").one()
        delta = np.frombuffer(row.delta, dtype=np.float32)
        assert row.votes_up == 6 and row.votes_down == 0
        # Six steps of 0.15 would be 0.9; the cap holds it at 0.35.
        assert abs(float(np.linalg.norm(delta)) - radio_taste.MAX_SHIFT) < 1e-3
        # The nudge points toward the station: the artist's tracks now fit the seed better.
        corrections = radio_taste.corrections_for(db, user_id, index)
        before = index.fit(radio_library["elsewhere"], context)
        after = index.fit(radio_library["elsewhere"], context, corrections)
        assert all(after[t] > before[t] for t in radio_library["elsewhere"])
        # Half a year on, half as strong; two years on, as good as gone.
        row.updated_at = datetime.utcnow() - timedelta(days=radio_taste.HALF_LIFE_DAYS)
        db.commit()
        radio_taste.reset  # noqa: B018 — keep the import used
        from app.services.recommendations.rec_cache import invalidate

        invalidate(f"radio_taste:{user_id}")
        halved = radio_taste.corrections_for(db, user_id, index)["elsewhere act"]
        assert abs(float(np.linalg.norm(halved)) - radio_taste.MAX_SHIFT / 2) < 1e-3
        assert radio_taste.summary(db, user_id) == {"artists": 1, "votes_up": 6, "votes_down": 0}
        assert radio_taste.reset(db, user_id) == 1
        assert radio_taste.summary(db, user_id)["artists"] == 0
    finally:
        db.close()


def test_a_thumb_on_a_station_is_remembered_on_the_account_and_can_be_reset(client, db_session_factory, radio_library):
    from app.models.listener_artist_correction import ListenerArtistCorrection
    from app.services import radio_taste

    user_id = radio_library["user_id"]
    db = db_session_factory()
    radio_taste.reset(db, user_id)
    db.close()

    seed = _make_track(db_session_factory, "/lib/radio-taste-seed.flac", title="Taste Seed", artist=ARTIST, album="Radio EP", track_number=11)
    _credit(db_session_factory, [seed], ARTIST, genre=GENRE)
    _build_map(db_session_factory)  # the seed is on the map, as it would be by the next night
    station = _station(client, seed_type="track", seed_track_id=seed)
    _next(client, station["id"])
    # The fixture's neighbours all carry the one tag and sit on one point of
    # the map, so a nudge among them has no direction; the corner with a
    # genre of its own does.
    elsewhere = radio_library["elsewhere"]
    assert client.post(f"/api/radio/stations/{station['id']}/feedback", json={"track_id": elsewhere[0], "kind": "less_artist"}).status_code == 200
    assert client.post(f"/api/radio/stations/{station['id']}/feedback", json={"track_id": elsewhere[1], "kind": "more"}).status_code == 200

    taste = client.get("/api/radio/taste")
    assert taste.status_code == 200
    body = taste.json()
    assert body["artists"] >= 1 and body["votes_down"] == 1 and body["votes_up"] == 1, body

    # The station goes; what it taught stays.
    assert client.delete(f"/api/radio/stations/{station['id']}").status_code == 200
    assert client.get("/api/radio/taste").json()["votes_down"] == 1

    # Said "less of" on this station: their tracks stay out of its batches
    # (that part was already true) — and the reset forgets the nudge.
    cleared = client.delete("/api/radio/taste")
    assert cleared.status_code == 200 and cleared.json()["cleared"] >= 1
    assert client.get("/api/radio/taste").json() == {"artists": 0, "votes_up": 0, "votes_down": 0, "cleared": None}
    db = db_session_factory()
    try:
        assert db.query(ListenerArtistCorrection).filter_by(user_id=user_id).count() == 0
    finally:
        db.close()


def test_less_of_an_artist_steers_the_next_batches_not_just_the_exclusion(client, db_session_factory, radio_library):
    """The map's version of "less": with the artist pushed out of the station's
    position, the station's query no longer leans their way at all."""
    import app.services.radio as radio

    seed = _make_track(db_session_factory, "/lib/radio-taste-seed-2.flac", title="Taste Seed 2", artist=ARTIST, album="Radio EP", track_number=12)
    _credit(db_session_factory, [seed], ARTIST, genre=GENRE)
    index = _build_map(db_session_factory)
    station = _station(client, seed_type="track", seed_track_id=seed)
    _next(client, station["id"])
    elsewhere = radio_library["elsewhere"]
    client.post(f"/api/radio/stations/{station['id']}/feedback", json={"track_id": elsewhere[0], "kind": "less_artist"})
    db = db_session_factory()
    try:
        from app.models.radio_station import RadioStation

        row = db.query(RadioStation).filter(RadioStation.id == station["id"]).one()
        feedback = radio.station_feedback(db, row)
        query, _ = radio.station_position(db, radio_library["user_id"], [seed], feedback)
        plain = index.query_from([seed])
        assert index.fit(elsewhere, query)[elsewhere[1]] < index.fit(elsewhere, plain)[elsewhere[1]]
        assert "elsewhere act" in feedback["less_artists"]
    finally:
        db.close()
    for _ in range(2):
        assert "Elsewhere Act" not in _artists(_next(client, station["id"])["tracks"])
