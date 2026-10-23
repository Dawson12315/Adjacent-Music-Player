"""Radio: a seed, a memory, and what next in batches.

The fixture library is one genre: an artist with two records, and forty
neighbours by other artists. Track radio opens with the seed and keeps the
seed artist to a fifth of the batch; album radio opens with the album;
artist radio keeps the artist to a quarter. What a station has played stays
out of the next batch, and a library too small to fill one says so.
"""

import pytest

from tests.test_for_you_rules import _stats, _user_id
from tests.test_pass_p import _admin, _make_track
from tests.test_track_numbers_and_dismissals import _credit

GENRE = "RadioGenre"
ARTIST = "Radio Act"
ALBUM = "Radio LP"


def _invalidate():
    from app.services.recommendations.rec_cache import invalidate_library_caches

    invalidate_library_caches()


@pytest.fixture(scope="module")
def radio_library(client, db_session_factory):
    _admin(client)
    user_id = _user_id(db_session_factory)

    lp = [
        _make_track(db_session_factory, f"/lib/radio-lp-{i}.flac", title=f"LP {i}", artist=ARTIST, album=ALBUM, track_number=i + 1)
        for i in range(6)
    ]
    ep = [
        _make_track(db_session_factory, f"/lib/radio-ep-{i}.flac", title=f"EP {i}", artist=ARTIST, album="Radio EP", track_number=i + 1)
        for i in range(6)
    ]
    _credit(db_session_factory, lp + ep, ARTIST, genre=GENRE)

    neighbours = []
    for i in range(40):
        track_id = _make_track(
            db_session_factory,
            f"/lib/radio-n-{i}.flac",
            title=f"Neighbour {i:02d}",
            artist=f"Neighbour Act {i % 8}",
            album=f"Neighbour Album {i % 5}",
        )
        _credit(db_session_factory, [track_id], f"Neighbour Act {i % 8}", genre=GENRE)
        neighbours.append(track_id)

    # A corner of the library radio should never reach.
    elsewhere = [
        _make_track(db_session_factory, f"/lib/radio-x-{i}.flac", title=f"Elsewhere {i}", artist="Elsewhere Act", album="Elsewhere")
        for i in range(5)
    ]
    _credit(db_session_factory, elsewhere, "Elsewhere Act", genre="ElsewhereGenre")

    # A little listening, so the behaviour channel and the "plays most"
    # ordering have something to go on.
    _stats(db_session_factory, user_id, lp[:3] + neighbours[:6], play_count=4, completion_count=3)
    _invalidate()

    yield {"user_id": user_id, "lp": lp, "ep": ep, "own": lp + ep, "neighbours": neighbours, "elsewhere": elsewhere}

    from app.models.radio_station import RadioStation, RadioStationPlay
    from app.models.track import Track
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre
    from app.models.track_user_stats import TrackUserStats

    ids = lp + ep + neighbours + elsewhere
    db = db_session_factory()
    try:
        for model in (TrackUserStats, TrackArtist, TrackGenre):
            db.query(model).filter(model.track_id.in_(ids)).delete(synchronize_session=False)
        db.query(RadioStationPlay).delete(synchronize_session=False)
        db.query(RadioStation).delete(synchronize_session=False)
        db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    _invalidate()


def _station(client, **seed):
    response = client.post("/api/radio/stations", json=seed)
    assert response.status_code == 200, response.text
    return response.json()


def _next(client, station_id, **params):
    response = client.get(f"/api/radio/stations/{station_id}/next", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_same_seed_is_one_station(client, radio_library):
    seed = radio_library["lp"][0]
    first = _station(client, seed_type="track", seed_track_id=seed)
    again = _station(client, seed_type="track", seed_track_id=seed)
    assert first["id"] == again["id"]
    assert first["name"] == "LP 0 radio"
    assert first["seed_track_id"] == seed


def test_a_seed_that_names_nothing_is_a_404(client, radio_library):
    assert client.post("/api/radio/stations", json={"seed_type": "track", "seed_track_id": 999999}).status_code == 404
    assert client.post("/api/radio/stations", json={"seed_type": "artist", "seed_artist": "Nobody At All"}).status_code == 404
    assert client.post("/api/radio/stations", json={"seed_type": "album", "seed_album": "No Such Record"}).status_code == 404
    assert client.get("/api/radio/stations/999999/next").status_code == 404


def test_track_radio_opens_with_the_seed_and_keeps_its_artist_to_a_fifth(client, radio_library):
    seed = radio_library["lp"][0]
    station = _station(client, seed_type="track", seed_track_id=seed)
    answer = _next(client, station["id"])
    tracks = answer["tracks"]
    ids = [track["id"] for track in tracks]

    assert len(tracks) == 20
    assert len(set(ids)) == 20
    assert ids[0] == seed
    assert tracks[0]["reason"] == "The track you started from"
    own = [track for track in tracks[1:] if track["id"] in set(radio_library["own"])]
    assert 1 <= len(own) <= 4
    assert all(track["reason"] == f"From {ARTIST}" for track in own)
    assert not set(ids) & set(radio_library["elsewhere"])
    assert answer["thin"] is False
    assert all(track["reason"] for track in tracks)


def test_artist_radio_opens_with_the_artist_and_keeps_them_to_a_quarter(client, radio_library):
    station = _station(client, seed_type="artist", seed_artist=ARTIST)
    assert station["name"] == f"{ARTIST} radio"
    tracks = _next(client, station["id"])["tracks"]
    ids = [track["id"] for track in tracks]
    own = set(radio_library["own"])

    assert len(tracks) == 20 and len(set(ids)) == 20
    assert ids[0] in own
    assert 2 <= len([track_id for track_id in ids if track_id in own]) <= 5
    assert not set(ids) & set(radio_library["elsewhere"])


def test_album_radio_opens_with_the_album_and_keeps_it_to_a_fifth(client, radio_library):
    station = _station(client, seed_type="album", seed_album=ALBUM, seed_album_artist=ARTIST)
    tracks = _next(client, station["id"])["tracks"]
    ids = [track["id"] for track in tracks]
    lp = set(radio_library["lp"])

    assert len(tracks) == 20 and len(set(ids)) == 20
    assert ids[0] in lp
    assert 1 <= len([track_id for track_id in ids if track_id in lp]) <= 4


def test_played_tracks_stay_out_and_stations_list_by_last_play(client, radio_library):
    seed = radio_library["lp"][1]
    station = _station(client, seed_type="track", seed_track_id=seed)
    first = [track["id"] for track in _next(client, station["id"])["tracks"]]

    reply = client.post(f"/api/radio/stations/{station['id']}/played", json={"track_ids": first})
    assert reply.status_code == 200, reply.text
    assert reply.json()["remembered"] == len(first)

    second = [track["id"] for track in _next(client, station["id"])["tracks"]]
    assert second, "the library still has unplayed neighbours"
    assert not set(second) & set(first)
    assert seed not in second

    # The queue the client already holds is kept out too.
    third = [track["id"] for track in _next(client, station["id"], exclude_track_ids=",".join(map(str, second)))["tracks"]]
    assert not set(third) & set(second)

    stations = client.get("/api/radio/stations").json()
    assert stations[0]["id"] == station["id"]
    assert stations[0]["name"] == "LP 1 radio"

    assert client.delete(f"/api/radio/stations/{station['id']}").status_code == 200
    assert client.get(f"/api/radio/stations/{station['id']}").status_code == 404
    assert station["id"] not in [item["id"] for item in client.get("/api/radio/stations").json()]


def test_a_small_corner_of_the_library_runs_thin_but_still_plays(client, radio_library):
    station = _station(client, seed_type="artist", seed_artist="Elsewhere Act")
    answer = _next(client, station["id"])
    ids = [track["id"] for track in answer["tracks"]]

    assert answer["thin"] is True
    assert ids, "a thin station still plays what it has"
    assert set(ids) <= set(radio_library["elsewhere"])
    assert len(set(ids)) == len(ids)


def test_an_exhausted_station_comes_round_again_rather_than_falling_silent(client, radio_library):
    station = _station(client, seed_type="artist", seed_artist="Elsewhere Act")
    first = [track["id"] for track in _next(client, station["id"])["tracks"]]
    assert first
    client.post(f"/api/radio/stations/{station['id']}/played", json={"track_ids": first})

    # Everything the corner holds has played; the client still holds it all.
    again = _next(client, station["id"], exclude_track_ids=",".join(map(str, first)))
    assert again["thin"] is True
    assert again["tracks"] == []

    # With the queue let go, the station repeats rather than stopping.
    once_more = _next(client, station["id"])
    ids = [track["id"] for track in once_more["tracks"]]
    assert ids and set(ids) <= set(radio_library["elsewhere"])
    assert all(track["reason"] for track in once_more["tracks"])
