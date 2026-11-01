"""Radio: a seed, a memory, and what next in batches.

The fixture library is mostly one genre: an artist with two records, and
forty neighbours by eight other artists. Off to the side: a five-track
corner in a genre of its own, an album tagged "Miscellaneous", and an album
with no tags at all. Track radio opens with the seed and keeps the seed
artist to a fifth of the batch; album radio opens with track one; artist
radio keeps the artist to a quarter. What a station has played, and what it
has handed out, stays out of the next batch; a corner too small to fill one
reaches wider and says so, and no station ever falls silent.
"""

import json

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

    # A corner of the library in a genre of its own.
    elsewhere = [
        _make_track(db_session_factory, f"/lib/radio-x-{i}.flac", title=f"Elsewhere {i}", artist="Elsewhere Act", album="Elsewhere")
        for i in range(5)
    ]
    _credit(db_session_factory, elsewhere, "Elsewhere Act", genre="ElsewhereGenre")

    # An album whose only tag says nothing, and one with no tag at all.
    misc = [
        _make_track(db_session_factory, f"/lib/radio-m-{i}.flac", title=f"Misc {i}", artist="Misc Act", album="Misc Album", track_number=i + 1)
        for i in range(4)
    ]
    _credit(db_session_factory, misc, "Misc Act", genre="Miscellaneous")
    quiet = [
        _make_track(db_session_factory, f"/lib/radio-q-{i}.flac", title=f"Quiet {i}", artist="Quiet Act", album="Quiet Album", track_number=i + 1)
        for i in range(4)
    ]
    _credit(db_session_factory, quiet, "Quiet Act")

    # A little listening, so the behaviour channel and the "plays most"
    # ordering have something to go on.
    _stats(db_session_factory, user_id, lp[:3] + neighbours[:6], play_count=4, completion_count=3)
    _invalidate()

    yield {
        "user_id": user_id,
        "lp": lp,
        "ep": ep,
        "own": lp + ep,
        "neighbours": neighbours,
        "elsewhere": elsewhere,
        "misc": misc,
        "quiet": quiet,
    }

    from app.models.radio_station import RadioStation, RadioStationFeedback, RadioStationPlay
    from app.models.track import Track
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre
    from app.models.track_user_stats import TrackUserStats

    ids = lp + ep + neighbours + elsewhere + misc + quiet
    db = db_session_factory()
    try:
        for model in (TrackUserStats, TrackArtist, TrackGenre):
            db.query(model).filter(model.track_id.in_(ids)).delete(synchronize_session=False)
        db.query(RadioStationPlay).delete(synchronize_session=False)
        db.query(RadioStationFeedback).delete(synchronize_session=False)
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


def _artists(tracks):
    return [track["artist"] for track in tracks]


def _no_artist_twice_in_a_row(tracks):
    artists = _artists(tracks)
    return all(a != b for a, b in zip(artists, artists[1:]))


# ------------------------------------------------------------------ stations


def test_the_same_seed_is_one_station_and_keeps_its_name(client, radio_library):
    seed = radio_library["lp"][0]
    first = _station(client, seed_type="track", seed_track_id=seed)
    again = _station(client, seed_type="track", seed_track_id=seed)
    assert first["id"] == again["id"]
    assert first["name"] == "LP 0 radio"
    assert first["seed_track_id"] == seed
    assert first["feedback"] == {"more_track_ids": [], "less_track_ids": [], "less_artists": []}

    # The same artist in a different casing is the same station, under the
    # name it was given first.
    one = _station(client, seed_type="artist", seed_artist=ARTIST)
    shouted = _station(client, seed_type="artist", seed_artist=f"  {ARTIST.upper()} ")
    assert one["id"] == shouted["id"]
    assert shouted["name"] == f"{ARTIST} radio"


def test_a_seed_that_names_nothing_is_a_404(client, radio_library):
    assert client.post("/api/radio/stations", json={"seed_type": "track", "seed_track_id": 999999}).status_code == 404
    assert client.post("/api/radio/stations", json={"seed_type": "artist", "seed_artist": "Nobody At All"}).status_code == 404
    assert client.post("/api/radio/stations", json={"seed_type": "album", "seed_album": "No Such Record"}).status_code == 404
    assert client.get("/api/radio/stations/999999/next").status_code == 404


def test_another_listeners_station_is_not_there(client, db_session_factory, radio_library):
    from app.models.radio_station import RadioStation

    db = db_session_factory()
    try:
        foreign = RadioStation(user_id=radio_library["user_id"] + 1000, seed_type="artist", seed_artist=ARTIST, seed_key="artist:foreign", name="Theirs")
        db.add(foreign)
        db.commit()
        foreign_id = foreign.id
    finally:
        db.close()

    assert client.get(f"/api/radio/stations/{foreign_id}").status_code == 404
    assert client.get(f"/api/radio/stations/{foreign_id}/next").status_code == 404
    assert client.get(f"/api/radio/stations/{foreign_id}/lineup").status_code == 404
    assert client.post(f"/api/radio/stations/{foreign_id}/played", json={"track_ids": [1]}).status_code == 404
    assert client.post(f"/api/radio/stations/{foreign_id}/feedback", json={"track_id": radio_library["lp"][0], "kind": "less"}).status_code == 404
    assert client.delete(f"/api/radio/stations/{foreign_id}").status_code == 404
    assert foreign_id not in [item["id"] for item in client.get("/api/radio/stations").json()]


def test_two_devices_starting_the_same_station_at_once_get_one_station(client, db_session_factory, radio_library, monkeypatch):
    """The read-then-insert loses its race: the insert hits the unique seed
    key, and the caller gets the row the other device made."""
    from app.schemas.radio import RadioStationCreate
    from app.services import radio

    existing = _station(client, seed_type="track", seed_track_id=radio_library["ep"][5])
    real_find = radio._find_station
    calls = {"n": 0}

    def find_none_once(db, user_id, key):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(db, user_id, key)

    monkeypatch.setattr(radio, "_find_station", find_none_once)
    db = db_session_factory()
    try:
        station = radio.get_or_create_station(
            db, radio_library["user_id"], RadioStationCreate(seed_type="track", seed_track_id=radio_library["ep"][5])
        )
        assert station is not None and station.id == existing["id"]
    finally:
        db.close()
    assert calls["n"] == 2


# ------------------------------------------------------------------- batches


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
    assert answer["reach"] is None
    assert all(track["reason"] for track in tracks)
    # The station speaks for itself, not for a playlist.
    assert not any("playlist" in (track["reason"] or "").lower() for track in tracks)


def test_a_batch_is_varied(client, radio_library):
    """No neighbour takes more than its cap of a batch, and no artist plays
    twice in a row — including the seed artist's own tracks, which are
    spread through the batch rather than bunched."""
    from collections import Counter

    station = _station(client, seed_type="track", seed_track_id=radio_library["ep"][0])
    tracks = _next(client, station["id"])["tracks"]
    counts = Counter(track["artist"] for track in tracks if track["artist"] != ARTIST)
    assert max(counts.values()) <= 3, counts
    assert _no_artist_twice_in_a_row(tracks), _artists(tracks)


def test_artist_radio_opens_with_the_artist_and_keeps_them_to_a_quarter(client, radio_library):
    station = _station(client, seed_type="artist", seed_artist=ARTIST)
    tracks = _next(client, station["id"])["tracks"]
    ids = [track["id"] for track in tracks]
    own = set(radio_library["own"])

    assert len(tracks) == 20 and len(set(ids)) == 20
    assert ids[0] in own
    assert 2 <= len([track_id for track_id in ids if track_id in own]) <= 5
    assert not set(ids) & set(radio_library["elsewhere"])
    assert _no_artist_twice_in_a_row(tracks), _artists(tracks)


def test_album_radio_opens_with_track_one_and_plays_the_album_in_order(client, radio_library):
    station = _station(client, seed_type="album", seed_album=ALBUM, seed_album_artist=ARTIST)
    tracks = _next(client, station["id"])["tracks"]
    ids = [track["id"] for track in tracks]
    lp = radio_library["lp"]

    assert len(tracks) == 20 and len(set(ids)) == 20
    assert ids[0] == lp[0], "track one opens"
    own = [track_id for track_id in ids if track_id in set(lp)]
    assert 1 <= len(own) <= 4
    assert own == sorted(own, key=lp.index), "the album's own tracks come round in order"
    assert all(track["reason"] == f"From {ALBUM}" for track in tracks if track["id"] in set(lp))


def test_a_batch_of_fifty_is_fifty(client, radio_library):
    station = _station(client, seed_type="track", seed_track_id=radio_library["lp"][5])
    answer = _next(client, station["id"], limit=50)
    ids = [track["id"] for track in answer["tracks"]]
    assert len(ids) == 50 and len(set(ids)) == 50


# -------------------------------------------------------------------- memory


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


def test_a_batch_handed_out_stays_out_even_before_it_is_reported(client, radio_library):
    """Two asks with nothing reported and nothing held are two different
    batches: what the station handed out counts, not only what the client
    got round to reporting."""
    station = _station(client, seed_type="track", seed_track_id=radio_library["lp"][4])
    first = [track["id"] for track in _next(client, station["id"])["tracks"]]
    second = [track["id"] for track in _next(client, station["id"])["tracks"]]
    assert first and second
    assert not set(first) & set(second)


def test_the_memory_counts_distinct_tracks_the_library_has(client, radio_library):
    station = _station(client, seed_type="track", seed_track_id=radio_library["ep"][1])
    first = [track["id"] for track in _next(client, station["id"])["tracks"]]

    once = client.post(f"/api/radio/stations/{station['id']}/played", json={"track_ids": first[:5]}).json()
    twice = client.post(f"/api/radio/stations/{station['id']}/played", json={"track_ids": first[:5]}).json()
    assert once["remembered"] == 5 and twice["remembered"] == 5

    junk = client.post(f"/api/radio/stations/{station['id']}/played", json={"track_ids": [999999, 0]}).json()
    assert junk["ok"] is True and junk["remembered"] == 5


# ------------------------------------------------------------------ reaching


def test_a_small_corner_reaches_wider_and_never_falls_silent(client, radio_library):
    """Five tracks in a genre of their own: the station plays them, then
    reaches to what the listener plays most, and says so. Everything played
    and everything held, it still answers; the queue let go, it comes round."""
    station = _station(client, seed_type="artist", seed_artist="Elsewhere Act")
    answer = _next(client, station["id"])
    tracks = answer["tracks"]
    ids = [track["id"] for track in tracks]
    corner = set(radio_library["elsewhere"])

    assert answer["thin"] is True
    assert answer["reach"] in {"artist", "listener", "library"}
    assert len(ids) == 20 and len(set(ids)) == 20
    assert ids[0] in corner and corner <= set(ids), "its own corner, spread through the batch"
    wider = [track for track in tracks if track["id"] not in corner]
    assert wider and all(track["reason"] in {"From what you play most", "Somewhere else in your library", "Further afield from Elsewhere Act"} for track in wider)

    client.post(f"/api/radio/stations/{station['id']}/played", json={"track_ids": ids})
    again = _next(client, station["id"], exclude_track_ids=",".join(map(str, ids)))
    again_ids = [track["id"] for track in again["tracks"]]
    assert again_ids, "holding everything it has played, the station still has somewhere to go"
    assert not set(again_ids) & set(ids)

    held = ids + again_ids
    client.post(f"/api/radio/stations/{station['id']}/played", json={"track_ids": again_ids})
    once_more = _next(client, station["id"], exclude_track_ids=",".join(map(str, held)))
    assert once_more["tracks"], "nor when it has to come back round"
    assert all(track["reason"] for track in once_more["tracks"])
    assert not set(track["id"] for track in once_more["tracks"]) & set(held)


def test_a_seed_whose_only_tag_says_nothing_is_not_walled_in(client, radio_library):
    """"Miscellaneous" is not a genre. The album plays, and the station
    draws the rest from the library rather than the four tracks that share
    the tag."""
    station = _station(client, seed_type="album", seed_album="Misc Album", seed_album_artist="Misc Act")
    answer = _next(client, station["id"])
    ids = [track["id"] for track in answer["tracks"]]
    assert len(ids) == 20 and len(set(ids)) == 20
    assert ids[0] == radio_library["misc"][0]
    assert len(set(ids) & set(radio_library["misc"])) <= 4 + 2
    assert len(set(ids) - set(radio_library["misc"])) >= 14

    second = _next(client, station["id"])
    assert len(second["tracks"]) == 20
    assert not {track["id"] for track in second["tracks"]} & set(ids)


def test_a_seed_with_no_tags_at_all_still_gets_a_station(client, radio_library):
    station = _station(client, seed_type="album", seed_album="Quiet Album", seed_album_artist="Quiet Act")
    answer = _next(client, station["id"])
    ids = [track["id"] for track in answer["tracks"]]
    assert len(ids) == 20 and len(set(ids)) == 20
    assert ids[0] == radio_library["quiet"][0]
    for _ in range(3):
        following = _next(client, station["id"])
        assert following["tracks"], "never an empty batch while the library has tracks"


def test_a_station_whose_seed_left_the_library_is_gone(client, db_session_factory, radio_library):
    from app.models.track import Track
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre

    doomed = _make_track(db_session_factory, "/lib/radio-doomed.flac", title="Doomed", artist="Doomed Act", album="Doomed")
    _credit(db_session_factory, [doomed], "Doomed Act", genre=GENRE)
    station = _station(client, seed_type="track", seed_track_id=doomed)
    assert _next(client, station["id"])["tracks"]

    db = db_session_factory()
    try:
        for model in (TrackArtist, TrackGenre):
            db.query(model).filter(model.track_id == doomed).delete(synchronize_session=False)
        db.query(Track).filter(Track.id == doomed).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    _invalidate()

    gone = client.get(f"/api/radio/stations/{station['id']}/next")
    assert gone.status_code == 410, gone.text


# ------------------------------------------------------------------ feedback


def test_the_listener_can_say_more_less_and_not_that_artist(client, radio_library):
    seed = radio_library["ep"][2]
    station = _station(client, seed_type="track", seed_track_id=seed)
    tracks = _next(client, station["id"])["tracks"]
    neighbour = next(track for track in tracks if track["artist"] != ARTIST)
    other_act = next(track for track in tracks if track["artist"] not in (ARTIST, neighbour["artist"]))

    less = client.post(f"/api/radio/stations/{station['id']}/feedback", json={"track_id": neighbour["id"], "kind": "less"})
    assert less.status_code == 200, less.text
    assert less.json()["less_track_ids"] == [neighbour["id"]]

    less_act = client.post(f"/api/radio/stations/{station['id']}/feedback", json={"track_id": other_act["id"], "kind": "less_artist"})
    assert less_act.status_code == 200, less_act.text
    assert less_act.json()["less_artists"] == [other_act["artist"]]

    more = client.post(f"/api/radio/stations/{station['id']}/feedback", json={"track_id": tracks[3]["id"], "kind": "more"})
    assert more.status_code == 200
    assert more.json()["more_track_ids"] == [tracks[3]["id"]]

    # The station carries what was said.
    assert client.get(f"/api/radio/stations/{station['id']}").json()["feedback"] == more.json()

    # "Less of" the station's own artist would empty it.
    own_track = next(track for track in tracks if track["artist"] == ARTIST)
    artist_station = _station(client, seed_type="artist", seed_artist=ARTIST)
    refused = client.post(f"/api/radio/stations/{artist_station['id']}/feedback", json={"track_id": own_track["id"], "kind": "less_artist"})
    assert refused.status_code == 409

    # From here on the track and the artist stay off this station, through
    # the memory and the come-round-again alike.
    for _ in range(4):
        batch = _next(client, station["id"])["tracks"]
        assert neighbour["id"] not in [track["id"] for track in batch]
        assert other_act["artist"] not in _artists(batch), _artists(batch)

    taken_back = client.delete(f"/api/radio/stations/{station['id']}/feedback", params={"track_id": other_act["id"], "kind": "less_artist"})
    assert taken_back.status_code == 200 and taken_back.json()["less_artists"] == []

    # "More" and "less" on one track replace each other.
    flipped = client.post(f"/api/radio/stations/{station['id']}/feedback", json={"track_id": tracks[3]["id"], "kind": "less"}).json()
    assert flipped["more_track_ids"] == [] and tracks[3]["id"] in flipped["less_track_ids"]


# -------------------------------------------------------------------- lineup


def test_a_station_keeps_its_lineup_and_the_place_the_listener_got_to(client, radio_library):
    # A seed no earlier test has played, so the station starts with nothing.
    station = _station(client, seed_type="track", seed_track_id=radio_library["lp"][3])
    # Nothing has played: nothing to continue.
    empty = client.get(f"/api/radio/stations/{station['id']}/lineup").json()
    assert empty["resumable"] is False and empty["tracks"] == []

    first = [track["id"] for track in _next(client, station["id"])["tracks"]]
    lineup = client.get(f"/api/radio/stations/{station['id']}/lineup").json()
    assert lineup["resumable"] is True
    assert [track["id"] for track in lineup["tracks"]] == first
    assert all(track["reason"] for track in lineup["tracks"])
    assert lineup["station"]["feedback"] is not None

    # The listener got to the fifth track: coming back starts there.
    client.post(f"/api/radio/stations/{station['id']}/played", json={"track_ids": first[:5]})
    lineup = client.get(f"/api/radio/stations/{station['id']}/lineup").json()
    assert [track["id"] for track in lineup["tracks"]] == first[4:]

    # The next batch joins the lineup behind the first.
    second = [track["id"] for track in _next(client, station["id"], exclude_track_ids=",".join(map(str, first)))["tracks"]]
    lineup = client.get(f"/api/radio/stations/{station['id']}/lineup").json()
    assert [track["id"] for track in lineup["tracks"]] == first[4:] + second


def test_a_lineup_older_than_ten_days_starts_over(client, db_session_factory, radio_library):
    from datetime import datetime, timedelta

    from app.models.radio_station import RadioStation

    station = _station(client, seed_type="track", seed_track_id=radio_library["lp"][2])
    assert _next(client, station["id"])["tracks"]
    assert client.get(f"/api/radio/stations/{station['id']}/lineup").json()["resumable"] is True

    db = db_session_factory()
    try:
        row = db.query(RadioStation).filter(RadioStation.id == station["id"]).one()
        row.lineup_saved_at = datetime.utcnow() - timedelta(days=11)
        db.commit()
    finally:
        db.close()

    stale = client.get(f"/api/radio/stations/{station['id']}/lineup").json()
    assert stale["resumable"] is False and stale["tracks"] == []


def test_the_lineup_position_moves_forward_through_repeats_and_trims_from_the_front():
    from datetime import datetime

    from app.models.radio_station import RadioStation
    from app.services import radio

    station = RadioStation(user_id=1, seed_type="artist", seed_artist="x", seed_key="artist:x", name="x radio")
    station.lineup_json = json.dumps([{"track_id": i, "reason": None} for i in list(range(1, 11)) + list(range(1, 11))])
    station.lineup_position = 0
    station.lineup_saved_at = datetime.utcnow()

    # Playing track 1 at row 0 stays at row 0, not row 10.
    radio._advance_lineup(station, [1])
    assert station.lineup_position == 0
    # Reaching tracks 3 and 4 moves to the furthest of them, ahead.
    radio._advance_lineup(station, [3, 4])
    assert station.lineup_position == 3
    # Track 1 again: its next appearance ahead, row 10.
    radio._advance_lineup(station, [1])
    assert station.lineup_position == 10
    # At the end, going back to track 7 lands on the nearest earlier appearance.
    station.lineup_position = 19
    radio._advance_lineup(station, [7])
    assert station.lineup_position == 16
    assert len(radio.remaining_lineup(station)) == 4

    class _Db:
        def commit(self):
            pass

    # Trimming keeps the newest LINEUP_MAX rows and the position with them.
    station.lineup_position = 15
    radio.extend_lineup(_Db(), station, [(100 + i, None) for i in range(radio.LINEUP_MAX)])
    rows = radio.lineup_of(station)
    assert len(rows) == radio.LINEUP_MAX
    assert rows[0]["track_id"] == 100 and station.lineup_position == 0


# --------------------------------------------------------------------- units


def test_interleave_spreads_own_tracks_evenly():
    from app.services import radio

    rows = radio._interleave(["a", "b", "c", "d"], [str(i) for i in range(16)])
    assert len(rows) == 20 and rows.count("a") == 1
    positions = [index for index, item in enumerate(rows) if item in {"a", "b", "c", "d"}]
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    assert positions[0] >= 2 and min(gaps) >= 4, positions


def test_spread_artists_keeps_the_opener_and_separates_neighbours():
    from app.services import radio

    rows = [(1, "open"), (2, "x"), (3, "x"), (4, "y"), (5, "y"), (6, "z")]
    artist_of = {1: "x", 2: "x", 3: "x", 4: "y", 5: "y", 6: "z"}
    spread = radio._spread_artists(rows, artist_of)
    assert spread[0] == (1, "open")
    artists = [artist_of[track_id] for track_id, _ in spread]
    assert sum(1 for a, b in zip(artists, artists[1:]) if a == b) <= 1, artists
    assert sorted(track_id for track_id, _ in spread) == [1, 2, 3, 4, 5, 6]


def test_tags_that_are_not_genres_are_left_out():
    from app.services.recommendations.genre_utils import is_non_genre_tag

    for tag in ("Miscellaneous", "misc", "Other", "Unknown", "0", "2020s", "80s", "1990's", "seen live", "Favorites", "Male Vocalist", ""):
        assert is_non_genre_tag(tag), tag
    for tag in ("Rock", "Hip-Hop", "Alternative R&B", "vaporwave", "Country", "Soundtrack"):
        assert not is_non_genre_tag(tag), tag
