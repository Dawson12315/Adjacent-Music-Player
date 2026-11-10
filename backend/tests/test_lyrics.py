"""Lyrics: read from the files, corrected by a person, timed and produced on
the server — and the routes and scanner paths that carry them."""

import json
import os
import shutil
import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "audio"
LRC = "[ar:Fen]\n[offset:0]\n[00:01.20]Long way round\n[00:04.80][00:12.00]Down the low country road\n[00:08.50]Night ferry <00:08.90>leaving\n"


@pytest.fixture()
def admin(client):
    client.post("/api/auth/setup-admin", json={"username": "admin", "password": "test-password-1"})
    assert client.post("/api/auth/login", json={"username": "admin", "password": "test-password-1"}).status_code == 200
    return client


def _delete_tracks_under(db_session_factory, prefix: str):
    from app.models.track import Track
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre
    from app.models.track_lyrics import TrackLyrics

    db = db_session_factory()
    try:
        ids = [row.id for row in db.query(Track.id).filter(Track.file_path.like(f"{prefix}%")).all()]
        if ids:
            for model in (TrackLyrics, TrackArtist, TrackGenre):
                db.query(model).filter(model.track_id.in_(ids)).delete(synchronize_session=False)
            db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Reading what the files carry
# ---------------------------------------------------------------------------


def test_lrc_is_parsed_into_timed_lines_and_plain_text():
    from app.services.lyrics_files import parse_lrc

    parsed = parse_lrc(LRC)
    assert parsed["synced"] == [
        [1.2, "Long way round"],
        [4.8, "Down the low country road"],
        [8.5, "Night ferry leaving"],
        [12.0, "Down the low country road"],
    ]
    assert parsed["plain"] == "Long way round\nDown the low country road\nNight ferry leaving\nDown the low country road"

    plain = parse_lrc("Just words\n\n\nmore words\n")
    assert plain == {"plain": "Just words\n\nmore words", "synced": None}

    shifted = parse_lrc("[offset:+500]\n[00:10.00]late\n")
    assert shifted["synced"] == [[9.5, "late"]]


def test_every_container_s_lyrics_tag_is_read(tmp_path):
    from mutagen import File
    from mutagen.id3 import ID3, SYLT, USLT, Encoding

    from app.services.lyrics_files import extract_lyrics_from_tags

    mp3 = tmp_path / "t.mp3"
    shutil.copy(FIXTURES / "tagged.mp3", mp3)
    tags = ID3(str(mp3))
    tags.add(USLT(encoding=Encoding.UTF8, lang="eng", desc="", text="Long way round\nDown the road"))
    tags.add(SYLT(encoding=Encoding.UTF8, lang="eng", format=2, type=1, text=[("Long way round", 1200), ("Down the road", 4800)]))
    tags.save()
    got = extract_lyrics_from_tags(str(mp3))
    assert got["plain"] == "Long way round\nDown the road"
    assert got["synced"] == [[1.2, "Long way round"], [4.8, "Down the road"]]

    m4a = tmp_path / "t.m4a"
    shutil.copy(FIXTURES / "tagged.m4a", m4a)
    audio = File(str(m4a))
    audio.tags["\xa9lyr"] = [LRC]
    audio.save()
    got = extract_lyrics_from_tags(str(m4a))
    assert got["synced"][0] == [1.2, "Long way round"], "LRC inside the tag is understood as timed"

    for name in ("tagged.flac", "tagged.ogg", "tagged.opus"):
        target = tmp_path / name
        shutil.copy(FIXTURES / name, target)
        audio = File(str(target))
        audio.tags["LYRICS"] = "Plain words\nSecond line"
        audio.save()
        got = extract_lyrics_from_tags(str(target))
        assert got == {"plain": "Plain words\nSecond line", "synced": None}, name

    assert extract_lyrics_from_tags(str(FIXTURES / "tagged.mp3")) is None


def test_a_sidecar_is_read_and_the_tag_wins_over_it(tmp_path):
    from mutagen.id3 import ID3, USLT, Encoding

    from app.services.lyrics_files import lyrics_from_file, sidecar_path_for

    song = tmp_path / "Artist - Song.mp3"
    shutil.copy(FIXTURES / "untagged.mp3", song)
    assert lyrics_from_file(str(song)) is None

    (tmp_path / "Artist - Song.lrc").write_text(LRC, encoding="utf-8")
    assert sidecar_path_for(str(song)).name == "Artist - Song.lrc"
    found = lyrics_from_file(str(song))
    assert found["source"] == "sidecar" and found["synced"][0] == [1.2, "Long way round"]

    tags = ID3(str(song))
    tags.add(USLT(encoding=Encoding.UTF8, lang="eng", desc="", text="From the tag"))
    tags.save()
    found = lyrics_from_file(str(song))
    assert found["source"] == "embedded" and found["plain"] == "From the tag"

    (tmp_path / "Other.txt").write_bytes("Plain sidecar\r\nline two".encode("utf-16"))
    shutil.copy(FIXTURES / "untagged.flac", tmp_path / "Other.flac")
    found = lyrics_from_file(str(tmp_path / "Other.flac"))
    assert found == {"source": "sidecar", "plain": "Plain sidecar\nline two", "synced": None}


# ---------------------------------------------------------------------------
# The scanner carries them
# ---------------------------------------------------------------------------


def test_the_scan_imports_backfills_and_follows_sidecars(client, db_session_factory, tmp_path, monkeypatch):
    from mutagen.id3 import ID3, USLT, Encoding

    from app.models.track import Track
    from app.models.track_lyrics import TrackLyrics
    from app.services import scanner

    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)
    lib = tmp_path / "lyrlib"
    lib.mkdir()
    tagged = lib / "Tagged.mp3"
    shutil.copy(FIXTURES / "tagged.mp3", tagged)
    tags = ID3(str(tagged))
    tags.add(USLT(encoding=Encoding.UTF8, lang="eng", desc="", text="Words in the tag"))
    tags.save()
    with_sidecar = lib / "Sidecar.flac"
    shutil.copy(FIXTURES / "tagged.flac", with_sidecar)
    (lib / "Sidecar.lrc").write_text(LRC, encoding="utf-8")
    bare = lib / "Bare.ogg"
    shutil.copy(FIXTURES / "tagged.ogg", bare)

    try:
        assert scanner.scan_directory(str(lib), limit=100)["added"] == 3

        def rows():
            db = db_session_factory()
            try:
                out = {}
                for track in db.query(Track).filter(Track.file_path.like(f"{lib}%")).all():
                    row = db.query(TrackLyrics).filter(TrackLyrics.track_id == track.id).first()
                    out[Path(track.file_path).name] = (
                        None if row is None else (row.source, row.plain, bool(row.synced)),
                        track.lyrics_checked_at is not None,
                        track.id,
                    )
                return out
            finally:
                db.close()

        state = rows()
        assert state["Tagged.mp3"][0] == ("embedded", "Words in the tag", False)
        assert state["Sidecar.flac"][0][0] == "sidecar" and state["Sidecar.flac"][0][2] is True
        assert state["Bare.ogg"][0] is None
        assert all(checked for _row, checked, _id in state.values()), "every new track was read for lyrics"

        # An older install: rows that were never read get read as the walk passes.
        db = db_session_factory()
        try:
            db.query(Track).filter(Track.file_path.like(f"{lib}%")).update({Track.lyrics_checked_at: None}, synchronize_session=False)
            db.query(TrackLyrics).filter(TrackLyrics.track_id == state["Tagged.mp3"][2]).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
        scanner.scan_directory(str(lib), limit=100)
        state = rows()
        assert state["Tagged.mp3"][0] == ("embedded", "Words in the tag", False)
        assert all(checked for _row, checked, _id in state.values())

        # A sidecar arriving later, newer than the last read, is picked up.
        time.sleep(0.05)
        bare_lrc = lib / "Bare.lrc"
        bare_lrc.write_text("[00:02.00]Bare words now\n", encoding="utf-8")
        future = time.time() + 5
        os.utime(bare_lrc, (future, future))
        scanner.scan_directory(str(lib), limit=100)
        state = rows()
        assert state["Bare.ogg"][0] == ("sidecar", "Bare words now", True)

        # A person's correction outranks the file and survives a rescan.
        db = db_session_factory()
        try:
            row = db.query(TrackLyrics).filter(TrackLyrics.track_id == state["Tagged.mp3"][2]).first()
            row.source = "user"
            row.plain = "Corrected words"
            db.commit()
        finally:
            db.close()
        future = time.time() + 10
        os.utime(tagged, (future, future))  # looks edited: the refresh path runs
        scanner.scan_directory(str(lib), limit=100)
        state = rows()
        assert state["Tagged.mp3"][0] == ("user", "Corrected words", False)
    finally:
        _delete_tracks_under(db_session_factory, str(lib))


# ---------------------------------------------------------------------------
# Timing known words, and reading the model's own
# ---------------------------------------------------------------------------


def _segments(words_with_times, no_speech=0.1, logprob=-0.3):
    words = [{"word": word, "start": at, "end": at + 0.3} for word, at in words_with_times]
    return [{"start": words[0]["start"], "end": words[-1]["end"], "text": " ".join(w["word"] for w in words), "words": words, "avg_logprob": logprob, "no_speech_prob": no_speech}]


def test_known_lines_take_the_time_of_their_first_heard_word():
    from app.services.lyrics_engine import align_lines

    known = "Long way round\nDown the low country road\nNight ferry leaving"
    heard = _segments(
        [("Long,", 2.0), ("way", 2.4), ("round", 2.8), ("down", 6.1), ("the", 6.3), ("low", 6.5), ("country", 6.8), ("road", 7.2), ("night", 9.9), ("fairy", 10.2), ("leaving", 10.6)]
    )
    out = align_lines(known, heard)
    assert [at for at, _line in out["synced"]] == [2.0, 6.1, 9.9]
    assert [line for _at, line in out["synced"]] == known.split("\n"), "the words are the known words, untouched"
    assert out["coverage"] > 0.85


def test_an_unheard_line_sits_between_its_neighbours_and_time_never_goes_backwards():
    from app.services.lyrics_engine import align_lines

    known = "first line here\nsomething the model missed\nthird line here"
    heard = _segments([("first", 1.0), ("line", 1.3), ("here", 1.6), ("third", 9.0), ("line", 9.3), ("here", 9.6)])
    out = align_lines(known, heard)
    times = [at for at, _line in out["synced"]]
    assert times[0] == 1.0 and times[2] == 9.0
    assert 1.0 < times[1] < 9.0
    assert times == sorted(times)
    assert out["coverage"] == pytest.approx(6 / 10)


def test_transcription_lines_come_from_the_kept_segments():
    from app.services.lyrics_engine import transcription_lines

    kept = _segments([("hello", 1.0), ("there", 1.4)]) + _segments([("second", 5.0), ("line", 5.3)], logprob=-0.5)
    out = transcription_lines(kept)
    assert out["synced"] == [[1.0, "hello there"], [5.0, "second line"]]
    assert out["plain"] == "hello there\nsecond line"
    assert out["words"] == 4 and 0.5 < out["confidence"] < 0.7
    assert transcription_lines([]) == {"synced": None, "plain": "", "words": 0, "confidence": None}


# ---------------------------------------------------------------------------
# The routes, the switch and the worker
# ---------------------------------------------------------------------------


@pytest.fixture()
def one_track(client, db_session_factory, tmp_path, monkeypatch):
    from app.models.track import Track
    from app.services import scanner

    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)
    lib = tmp_path / "routelib"
    lib.mkdir()
    shutil.copy(FIXTURES / "tagged.mp3", lib / "Route.mp3")
    scanner.scan_directory(str(lib), limit=10)
    db = db_session_factory()
    try:
        track_id = db.query(Track.id).filter(Track.file_path == str(lib / "Route.mp3")).scalar()
    finally:
        db.close()
    yield {"id": track_id, "path": lib / "Route.mp3", "lib": lib}
    _delete_tracks_under(db_session_factory, str(lib))


def test_no_lyrics_says_whether_the_server_could_make_some(admin, one_track, monkeypatch):
    from app.services import lyrics_engine, lyrics_runner

    monkeypatch.setattr(lyrics_engine, "transcriber_available", lambda: False)
    response = admin.get(f"/api/tracks/{one_track['id']}/lyrics")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "no_lyrics"
    assert response.json()["detail"]["generation"]["state"] == "unsupported"
    assert admin.post(f"/api/tracks/{one_track['id']}/lyrics/generate").status_code == 409

    monkeypatch.setattr(lyrics_engine, "transcriber_available", lambda: True)
    monkeypatch.setattr(lyrics_runner, "generation_settings", lambda: (False, "base"))
    assert admin.get(f"/api/tracks/{one_track['id']}/lyrics").json()["detail"]["generation"]["state"] == "off"
    refused = admin.post(f"/api/tracks/{one_track['id']}/lyrics/generate")
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "generation_off"

    assert "lyrics" in admin.get("/api/health").json()["capabilities"]


def test_the_settings_carry_the_switch_the_model_and_the_time(admin):
    current = admin.get("/api/settings").json()
    assert current["lyrics_generation_enabled"] is False and current["lyrics_model"] == "base"
    payload = {key: value for key, value in current.items() if not key.endswith("_set")}
    payload.update({"lyrics_generation_enabled": True, "lyrics_model": "small", "lyrics_time": "03:15"})
    saved = admin.put("/api/settings", json=payload).json()
    assert (saved["lyrics_generation_enabled"], saved["lyrics_model"], saved["lyrics_time"]) == (True, "small", "03:15")
    # An unknown model falls back; an old client leaving the fields out keeps them.
    payload["lyrics_model"] = "enormous"
    assert admin.put("/api/settings", json=payload).json()["lyrics_model"] == "base"
    for key in ("lyrics_generation_enabled", "lyrics_model", "lyrics_time"):
        payload.pop(key)
    kept = admin.put("/api/settings", json=payload).json()
    assert kept["lyrics_generation_enabled"] is True and kept["lyrics_time"] == "03:15"
    payload.update({"lyrics_generation_enabled": False, "lyrics_time": ""})
    off = admin.put("/api/settings", json=payload).json()
    assert off["lyrics_generation_enabled"] is False and off["lyrics_time"] is None


def test_a_person_s_words_are_saved_understood_as_lrc_and_can_be_undone(admin, one_track):
    track_id = one_track["id"]
    saved = admin.put(f"/api/tracks/{track_id}/lyrics", json={"plain": LRC}).json()
    assert saved["source"] == "user" and saved["synced_source"] == "user" and saved["generated"] is False
    assert saved["synced"][0] == {"t": 1.2, "line": "Long way round"}
    assert admin.get(f"/api/tracks/{track_id}/lyrics").json()["plain"].startswith("Long way round")

    timed = admin.put(f"/api/tracks/{track_id}/lyrics", json={"synced": [{"t": 9, "line": "later"}, {"t": 3, "line": "sooner"}]}).json()
    assert [line["line"] for line in timed["synced"]] == ["sooner", "later"], "lines are kept in time order"
    assert timed["plain"] == "sooner\nlater"

    assert admin.put(f"/api/tracks/{track_id}/lyrics", json={"plain": "   "}).status_code == 422

    # Undo: back to what the file says — which is nothing, for this fixture.
    gone = admin.delete(f"/api/tracks/{track_id}/lyrics")
    assert gone.status_code == 404 and gone.json()["detail"]["code"] == "no_lyrics"

    status = admin.get("/api/lyrics/status").json()
    assert {"tracks", "with_lyrics", "timed", "by_source", "generation"} <= set(status)


def test_the_worker_times_known_words_and_transcribes_the_rest(admin, one_track, db_session_factory, monkeypatch):
    from app.models.track_lyrics import TrackLyrics
    from app.services import lyrics_engine, lyrics_runner

    track_id = one_track["id"]
    monkeypatch.setattr(lyrics_engine, "transcriber_available", lambda: True)
    monkeypatch.setattr(lyrics_runner, "generation_settings", lambda: (True, "base"))
    monkeypatch.setattr("app.services.stream_cache_maintenance.has_room_for_transcode", lambda: True)
    calls = []

    def fake_generate(file_path, *, model_name, known_text=None):
        calls.append((Path(file_path).name, model_name, known_text))
        if known_text:
            return {"ok": True, "kind": "aligned", "synced": [[1.0, line] for line in known_text.split("\n")], "plain": known_text, "confidence": 0.9, "language": "en", "model": model_name}
        return {"ok": True, "kind": "transcribed", "synced": [[0.5, "heard words"], [4.0, "more heard words"]], "plain": "heard words\nmore heard words", "confidence": 0.7, "language": "en", "model": model_name}

    monkeypatch.setattr(lyrics_engine, "generate", fake_generate)

    # Nothing known: words and timing from the audio.
    status = lyrics_runner.request_generation(track_id)
    assert status["state"] in ("queued", "running")
    deadline = time.time() + 10
    while time.time() < deadline and admin.get(f"/api/tracks/{track_id}/lyrics").status_code == 404:
        time.sleep(0.05)
    got = admin.get(f"/api/tracks/{track_id}/lyrics").json()
    assert got["source"] == "transcribed" and got["generated"] is True and got["model"] == "base"
    assert got["synced"][1] == {"t": 4.0, "line": "more heard words"}
    assert calls[-1] == ("Route.mp3", "base", None)

    # Known words without timing: only the timing is produced; the words stay.
    db = db_session_factory()
    try:
        row = db.query(TrackLyrics).filter(TrackLyrics.track_id == track_id).first()
        row.source, row.synced_source, row.plain, row.synced, row.model = "embedded", None, "Known line one\nKnown line two", None, None
        db.commit()
    finally:
        db.close()
    assert admin.post(f"/api/tracks/{track_id}/lyrics/generate").status_code == 202
    deadline = time.time() + 10
    while time.time() < deadline and not admin.get(f"/api/tracks/{track_id}/lyrics").json().get("synced"):
        time.sleep(0.05)
    got = admin.get(f"/api/tracks/{track_id}/lyrics").json()
    assert got["source"] == "embedded" and got["synced_source"] == "aligned" and got["generated"] is True
    assert got["plain"] == "Known line one\nKnown line two"
    assert calls[-1] == ("Route.mp3", "base", "Known line one\nKnown line two")
    # Already timed: a second request is a no-op.
    assert admin.post(f"/api/tracks/{track_id}/lyrics/generate").json()["state"] == "done"


def test_a_failed_generation_is_remembered_with_its_reason(admin, one_track, monkeypatch):
    from app.services import lyrics_engine, lyrics_runner

    track_id = one_track["id"]
    monkeypatch.setattr(lyrics_engine, "transcriber_available", lambda: True)
    monkeypatch.setattr(lyrics_runner, "generation_settings", lambda: (True, "base"))
    monkeypatch.setattr("app.services.stream_cache_maintenance.has_room_for_transcode", lambda: True)
    monkeypatch.setattr(lyrics_engine, "generate", lambda *a, **k: {"ok": False, "reason": "No vocals were found in this track."})

    lyrics_runner.request_generation(track_id)
    deadline = time.time() + 10
    while time.time() < deadline and lyrics_runner.track_generation_status(track_id)["state"] != "failed":
        time.sleep(0.05)
    status = admin.get(f"/api/tracks/{track_id}/lyrics").json()["detail"]["generation"]
    assert status == {"state": "failed", "reason": "No vocals were found in this track."}
    progress = lyrics_runner.get_progress()
    assert progress["failed"] >= 1 and progress["last_error"] == "No vocals were found in this track."


def test_the_nightly_queue_takes_the_most_played_tracks_without_lyrics(client, db_session_factory, tmp_path, monkeypatch):
    from app.models.track import Track
    from app.models.track_lyrics import TrackLyrics
    from app.models.track_user_stats import TrackUserStats
    from app.services import lyrics_engine, lyrics_runner, scanner

    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)
    monkeypatch.setattr(lyrics_engine, "transcriber_available", lambda: True)
    monkeypatch.setattr(lyrics_runner, "generation_settings", lambda: (True, "base"))
    started = []
    monkeypatch.setattr(lyrics_runner, "_ensure_worker", lambda budget_seconds=None: started.append(budget_seconds))
    # The shared test database holds every other test's tracks, most without
    # lyrics and some with play counts; the batch cap must not decide this.
    monkeypatch.setattr(lyrics_runner, "NIGHTLY_BATCH", 100_000)
    lyrics_runner._failures.clear()

    lib = tmp_path / "nightlib"
    lib.mkdir()
    for name in ("A.mp3", "B.mp3", "C.mp3"):
        shutil.copy(FIXTURES / "untagged.mp3", lib / name)
    scanner.scan_directory(str(lib), limit=10)
    try:
        db = db_session_factory()
        try:
            ids = {Path(t.file_path).name: t.id for t in db.query(Track).filter(Track.file_path.like(f"{lib}%")).all()}
            db.add(TrackUserStats(track_id=ids["B.mp3"], play_count=9))
            db.add(TrackUserStats(track_id=ids["C.mp3"], play_count=2))
            db.add(TrackLyrics(track_id=ids["A.mp3"], source="embedded", plain="has words"))
            db.commit()
        finally:
            db.close()
        with lyrics_runner._guard:
            lyrics_runner._queue.clear()
            lyrics_runner._queued.clear()
        added = lyrics_runner.enqueue_nightly()
        assert added >= 2
        queued = list(lyrics_runner._queue)
        assert queued.index(ids["B.mp3"]) < queued.index(ids["C.mp3"]), "most played first"
        assert ids["A.mp3"] not in queued, "tracks with words are not queued"
        assert started == [lyrics_runner.NIGHTLY_BUDGET_SECONDS]
    finally:
        with lyrics_runner._guard:
            lyrics_runner._queue.clear()
            lyrics_runner._queued.clear()
        _delete_tracks_under(db_session_factory, str(lib))
