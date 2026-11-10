"""Audio analysis: what a track sounds like (librosa), what its vocals say
about it (the flags), what its words are about (the words block), and how
stations and the recommender read all three."""

import numpy as np
import pytest

from tests.test_pass_p import _make_track

PREFIX = "/audio-tests/"


@pytest.fixture()
def admin(client):
    client.post("/api/auth/setup-admin", json={"username": "admin", "password": "test-password-1"})
    assert client.post("/api/auth/login", json={"username": "admin", "password": "test-password-1"}).status_code == 200
    return client


@pytest.fixture(autouse=True, scope="module")
def _clean_up(client, db_session_factory):
    # `client` first: the app's startup creates the tables this module writes to.
    yield
    from app.models.track import Track
    from app.models.track_audio_profile import TrackAudioProfile, TrackFeatureVector
    from app.models.track_lyrics import TrackLyrics
    from app.models.track_user_stats import TrackUserStats

    db = db_session_factory()
    try:
        ids = [row.id for row in db.query(Track.id).filter(Track.file_path.like(f"{PREFIX}%")).all()]
        if ids:
            for model in (TrackAudioProfile, TrackFeatureVector, TrackLyrics, TrackUserStats):
                db.query(model).filter(model.track_id.in_(ids)).delete(synchronize_session=False)
            db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _track(db_session_factory, name, **fields):
    return _make_track(db_session_factory, f"{PREFIX}{name}.flac", title=name, **fields)


def _set(db_session_factory, track_id, **fields):
    from app.models.track import Track

    db = db_session_factory()
    try:
        track = db.query(Track).filter(Track.id == track_id).first()
        for key, value in fields.items():
            setattr(track, key, value)
        db.commit()
    finally:
        db.close()


def _get(db_session_factory, track_id):
    from app.models.track import Track

    db = db_session_factory()
    try:
        track = db.query(Track).filter(Track.id == track_id).first()
        db.expunge(track)
        return track
    finally:
        db.close()


# ------------------------------------------------------------- the sound


def test_the_measurement_hears_tempo_and_brightness_in_synthetic_signals():
    from app.services import audio_features

    if not audio_features.profiler_available():
        pytest.skip("librosa is not installed here")
    sr = audio_features.SAMPLE_RATE
    seconds = 20
    rng = np.random.default_rng(1)
    # A click track at 120 bpm: a short noise burst every half second.
    click = np.zeros(sr * seconds, dtype=np.float32)
    burst = (rng.standard_normal(400) * np.exp(-np.arange(400) / 80.0)).astype(np.float32)
    for beat in range(seconds * 2):
        start = int(beat * 0.5 * sr)
        click[start : start + 400] = burst
    clicks = audio_features.features_from_samples(click)
    tempo = float(clicks[0])
    assert clicks.shape == (audio_features.FEATURE_COUNT,)
    # Within an octave of 120: beat trackers halve and double, the map folds.
    assert min(abs(np.log2(tempo / 120.0) - k) for k in (-1, 0, 1)) < 0.1

    t = np.arange(0, seconds, 1.0 / sr)
    sine = np.sin(2 * np.pi * 220.0 * t).astype(np.float32)
    tone = audio_features.features_from_samples(sine)
    names = list(audio_features.FEATURE_NAMES)
    assert tone[names.index("flatness")] < clicks[names.index("flatness")]  # a sine is tonal, noise is flat
    assert tone[names.index("centroid")] < clicks[names.index("centroid")]  # and darker than noise bursts


def test_standardised_profiles_fold_tempo_by_octave_and_come_out_unit():
    from app.services import audio_features

    # Every feature but tempo identical, so only tempo tells the rows apart.
    raw = np.ones((6, audio_features.FEATURE_COUNT), dtype=np.float32)
    raw[:, 0] = [60.0, 120.0, 90.0, 100.0, 140.0, 75.0]
    vectors = audio_features.standardise_profiles(raw)
    assert vectors.shape == (6, audio_features.SOUND_DIMENSIONS)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
    # 60 and 120 share the folded circle; 60 and 90 do not.
    assert float(vectors[0] @ vectors[1]) > float(vectors[0] @ vectors[2])


def test_excerpts_combine_with_the_median_tempo():
    from app.services import audio_features

    a = np.ones(audio_features.FEATURE_COUNT, dtype=np.float32)
    b = a.copy()
    c = a.copy()
    a[0], b[0], c[0] = 100.0, 200.0, 100.0
    b[1] = 4.0
    out = audio_features.combine_excerpts([a, b, c])
    assert out[0] == 100.0
    assert out[1] == pytest.approx(2.0)


# ------------------------------------------------------------- the words


def test_the_words_block_puts_songs_about_the_same_thing_together():
    from app.services.recommendations.word_map import build_word_vectors

    sea = "sea waves sailing harbour tide salt gulls anchor rope water deep blue"
    road = "engine highway driving wheels gasoline miles asphalt headlights truck night fast"
    filler = ["morning coffee kitchen window sunlight quiet table bread", "mountain snow climbing rope summit cold wind sky",
              "garden roses thorns petals summer bees honey", "city subway crowd neon rain umbrella taxi",
              "letter paper ink stamp mailbox waiting answer", "guitar strings chords practice bedroom amplifier"]
    docs = {}
    for i in range(3):
        docs[i] = f"{sea} chorus {i} again"
        docs[10 + i] = f"{road} chorus {i} again"
    for i, text in enumerate(filler):
        docs[100 + i] = text + " something else entirely here"
    ids, vectors = build_word_vectors(docs, dimensions=4)
    rows = {track_id: vectors[i] for i, track_id in enumerate(ids)}
    assert all(track_id in rows for track_id in (0, 1, 10, 11))
    assert float(rows[0] @ rows[1]) > float(rows[0] @ rows[10])
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


# ------------------------------------------------------------- the flags


def test_explicit_detection_stops_at_word_boundaries():
    from app.services import track_flags

    assert track_flags.explicit_from_text("what the fuck is this") == "explicit"
    assert track_flags.explicit_from_text("the class assignment is due") == "clean"
    assert track_flags.explicit_from_text("we drove through Scunthorpe") == "clean"
    assert track_flags.explicit_from_text("") is None
    assert track_flags.explicit_from_text("La puta madre") == "explicit"


def test_detected_flags_never_overwrite_an_admins(db_session_factory):
    from app.services import track_flags

    track_id = _track(db_session_factory, "locked")
    db = db_session_factory()
    try:
        from app.models.track import Track

        track = db.query(Track).filter(Track.id == track_id).first()
        assert track_flags.apply_detected(db, track, vocal_state="vocal", language="en", language_confidence=0.9)
        db.commit()
        assert track.flags_set_by == "detected"
        track_flags.set_by_admin(db, track, vocal_state="instrumental")
        assert not track_flags.apply_detected(db, track, vocal_state="vocal")
        assert track.vocal_state == "instrumental" and track.flags_set_by == "admin"
        # Words arriving set the explicit flag on a detected track, not a locked one.
        track_flags.note_lyrics_text(db, track_id, "we went down to the sea")
        assert track.explicit_state is None
    finally:
        db.close()

    other = _track(db_session_factory, "words")
    db = db_session_factory()
    try:
        track_flags.note_lyrics_text(db, other, "what the fuck")
        row = _get(db_session_factory, other)
        assert (row.explicit_state, row.vocal_state, row.flags_set_by) == ("explicit", "vocal", "detected")
        track_flags.note_lyrics_text(db, other, None)
        assert _get(db_session_factory, other).explicit_state is None
    finally:
        db.close()


class _Segment:
    def __init__(self, text, logprob=-0.3, no_speech=0.1, compression=1.3):
        self.text = text
        self.no_speech_prob = no_speech
        self.avg_logprob = logprob
        self.compression_ratio = compression


class _FakeModel:
    """One segment per window: `words_per_window` counts, or ready segments."""

    def __init__(self, language, confidence, words_per_window):
        self.language = language
        self.confidence = confidence
        self.windows = list(words_per_window)

    def detect_language(self, audio):
        return self.language, self.confidence, {}

    def transcribe(self, audio, **kwargs):
        item = self.windows.pop(0) if self.windows else 0
        if isinstance(item, _Segment):
            return [item], None
        return ([_Segment(" ".join(f"word{i}" for i in range(item)))] if item else []), None


def test_detection_decides_vocal_instrumental_or_undecided(monkeypatch):
    from app.services import lyrics_engine, track_flags

    monkeypatch.setattr(track_flags, "_decode_window", lambda path, start, seconds: np.zeros(16000 * 30, dtype=np.float32))

    monkeypatch.setattr(lyrics_engine, "load_model", lambda name: _FakeModel("es", 0.92, [12]))
    sung = track_flags.detect("/nowhere.flac", 240.0, "base")
    assert (sung["vocal_state"], sung["language"], sung["language_confidence"]) == ("vocal", "es", 0.92)

    monkeypatch.setattr(lyrics_engine, "load_model", lambda name: _FakeModel("en", 0.99, [0, 1]))
    quiet = track_flags.detect("/nowhere.flac", 240.0, "base")
    assert quiet["vocal_state"] == "instrumental" and quiet["language"] is None

    # Three words in a window: too many to call it instrumental, too few to
    # call it a song. Unknown, which the radio treats as neither.
    monkeypatch.setattr(lyrics_engine, "load_model", lambda name: _FakeModel("en", 0.99, [3, 3]))
    unsure = track_flags.detect("/nowhere.flac", 240.0, "base")
    assert unsure["vocal_state"] is None and unsure["language"] is None

    # Sure of the words, unsure of the language: the language is left out.
    monkeypatch.setattr(lyrics_engine, "load_model", lambda name: _FakeModel("de", 0.3, [20]))
    shy = track_flags.detect("/nowhere.flac", 240.0, "base")
    assert shy["vocal_state"] == "vocal" and shy["language"] is None

    # What a pure tone sounds like to Whisper: a confident-looking language,
    # a word or two per window at a log-probability near -2. Not a song.
    tone = _FakeModel("en", 0.7, [_Segment("you", logprob=-2.1), _Segment("...", logprob=-2.0)])
    monkeypatch.setattr(lyrics_engine, "load_model", lambda name: tone)
    assert track_flags.detect("/nowhere.flac", 150.0, "base")["vocal_state"] == "instrumental"
    # Hallucinated words do not add up across windows into a song.
    drift = _FakeModel("en", 0.7, [4, 4])
    monkeypatch.setattr(lyrics_engine, "load_model", lambda name: drift)
    assert track_flags.detect("/nowhere.flac", 150.0, "base")["vocal_state"] is None
    # A chorus of one word over and over is not enough to call vocal either.
    chant = _FakeModel("en", 0.9, [_Segment(" ".join(["la"] * 12))])
    monkeypatch.setattr(lyrics_engine, "load_model", lambda name: chant)
    assert track_flags.detect("/nowhere.flac", 150.0, "base")["vocal_state"] is None


def test_a_full_lyrics_pass_yields_the_flags_for_free():
    from app.services import track_flags

    sung = track_flags.flags_from_lyrics_result({"ok": True, "language": "en", "language_probability": 0.8, "plain": "oh shit"})
    assert sung == {"vocal_state": "vocal", "language": "en", "language_confidence": 0.8, "explicit_state": "explicit"}
    assert track_flags.flags_from_lyrics_result({"ok": False, "instrumental": True}) == {"vocal_state": "instrumental"}
    assert track_flags.flags_from_lyrics_result({"ok": False, "reason": "nope"}) == {}


# ------------------------------------------------------------- the index


def _index():
    from app.services.recommendations.vector_map import VectorIndex

    ids = np.asarray([1, 2, 3], dtype=np.int64)
    matrix = np.asarray([[1.0, 0.0], [0.6, 0.8], [0.0, 1.0]], dtype=np.float32)
    sound = np.asarray([[1.0, 0.0], [1.0, 0.0], [0.0, 0.0]], dtype=np.float32)  # track 3 has no profile
    return VectorIndex(
        ids=ids,
        matrix=matrix,
        position={1: 0, 2: 1, 3: 2},
        artist_keys=[],
        artist_matrix=np.zeros((0, 2), dtype=np.float32),
        artist_position={},
        dim=2,
        track_artist=["a", "b", "c"],
        blocks={"sound": sound},
    )


def test_blended_nearness_renormalises_over_the_blocks_a_track_has():
    from app.services.recommendations.vector_map import STATION_SHARES

    index = _index()
    query = np.asarray([1.0, 0.0], dtype=np.float32)
    blend = index.blend_for([1])
    assert set(blend) == {"sound"}
    scores = dict(index.nearest(query, 3, blend=blend))
    # Track 2: map cosine 0.6 and sound cosine 1.0, mixed at the shares.
    expected_2 = (0.6 * STATION_SHARES["map"] + 1.0 * STATION_SHARES["sound"]) / (STATION_SHARES["map"] + STATION_SHARES["sound"])
    assert scores[2] == pytest.approx(expected_2, abs=1e-5)
    # Track 3 has no sound profile: judged by the map alone, not pushed away.
    assert scores[3] == pytest.approx(0.0, abs=1e-6)
    assert dict(index.nearest(query, 3))[2] == pytest.approx(0.6, abs=1e-6)
    assert index.block_query("sound", [3]) is None
    assert index.block_query("words", [1]) is None
    assert [track_id for track_id, _ in index.block_nearest("sound", query, 5)] == [1, 2]
    assert index.fit([2, 3], query, blend=blend)[2] == pytest.approx(expected_2, abs=1e-5)


# ------------------------------------------------------------- the station


def test_a_station_keeps_its_seeds_vocal_state_and_language(db_session_factory):
    from app.services.radio import StationFilter

    seed = _track(db_session_factory, "seed-es", vocal_state="vocal", language="es", language_confidence=0.9)
    english = _track(db_session_factory, "cand-en", vocal_state="vocal", language="en", language_confidence=0.9)
    instrumental = _track(db_session_factory, "cand-inst", vocal_state="instrumental")
    unknown = _track(db_session_factory, "cand-unknown")
    spanish = _track(db_session_factory, "cand-es", vocal_state="vocal", language="es", language_confidence=0.7)
    inst_seed = _track(db_session_factory, "seed-inst", vocal_state="instrumental")
    db = db_session_factory()
    try:
        seed_track = _get(db_session_factory, seed)
        kept = StationFilter(db, [seed_track], user_id=None).keep([english, instrumental, unknown, spanish])
        assert kept == [unknown, spanish]

        kept = StationFilter(db, [_get(db_session_factory, inst_seed)], user_id=None).keep([english, instrumental, unknown, spanish])
        assert kept == [instrumental, unknown]

        # Mixed seeds (an artist with songs and instrumentals) set no vocal
        # rule; the language of the sung ones still holds.
        mixed = StationFilter(db, [seed_track, _get(db_session_factory, inst_seed)], user_id=None)
        assert mixed.vocal_state is None and mixed.languages == {"es"}
        assert mixed.keep([english, instrumental, spanish, unknown]) == [instrumental, spanish, unknown]

        # A language the model was unsure of is not a rule either.
        shy = _track(db_session_factory, "seed-shy", vocal_state="vocal", language="fr", language_confidence=0.4)
        assert StationFilter(db, [_get(db_session_factory, shy)], user_id=None).languages == set()
    finally:
        db.close()


def test_a_listener_who_plays_in_two_languages_is_not_held_to_one(db_session_factory, admin):
    from app.models.track_user_stats import TrackUserStats
    from app.models.user import User
    from app.services.radio import StationFilter

    db = db_session_factory()
    try:
        user_id = db.query(User.id).filter(User.username == "admin").scalar()
        en = _track(db_session_factory, "mix-en", vocal_state="vocal", language="en", language_confidence=0.9)
        es = _track(db_session_factory, "mix-es", vocal_state="vocal", language="es", language_confidence=0.9)
        db.add(TrackUserStats(user_id=user_id, track_id=en, play_count=30))
        db.add(TrackUserStats(user_id=user_id, track_id=es, play_count=30))
        db.commit()
        seed = _get(db_session_factory, es)
        assert StationFilter(db, [seed], user_id=None).languages == {"es"}
        assert StationFilter(db, [seed], user_id=user_id).languages == set()
    finally:
        db.close()


# ------------------------------------------------------------- the runner


def test_the_runner_measures_once_and_remembers(db_session_factory, monkeypatch):
    from app.models.track_audio_profile import TrackAudioProfile
    from app.services import audio_analysis, audio_features, track_flags

    track_id = _track(db_session_factory, "runner", duration_seconds=200.0)
    monkeypatch.setattr(audio_features, "profiler_available", lambda: True)
    monkeypatch.setattr(track_flags, "flags_available", lambda: True)
    monkeypatch.setattr(audio_analysis, "analysis_settings", lambda: (True, "03:30", "base"))
    measured = {"sound": 0, "flags": 0}

    def fake_profile(path, duration):
        measured["sound"] += 1
        return np.arange(audio_features.FEATURE_COUNT, dtype=np.float32)

    def fake_detect(path, duration, model):
        measured["flags"] += 1
        return {"vocal_state": "vocal", "language": "en", "language_confidence": 0.8, "words": 20}

    monkeypatch.setattr(audio_features, "profile_file", fake_profile)
    monkeypatch.setattr(track_flags, "detect", fake_detect)

    assert audio_analysis._analyse_one(track_id) == "ok"
    db = db_session_factory()
    try:
        row = db.query(TrackAudioProfile).filter(TrackAudioProfile.track_id == track_id).first()
        assert row.version == audio_features.PROFILE_VERSION and row.feature_count == audio_features.FEATURE_COUNT
        assert audio_features.unpack(row.features, row.feature_count)[3] == 3.0
    finally:
        db.close()
    track = _get(db_session_factory, track_id)
    assert (track.vocal_state, track.language, track.flags_set_by) == ("vocal", "en", "detected")
    assert track.flags_checked_at is not None

    # Measured already: nothing is listened to again.
    assert audio_analysis._analyse_one(track_id) == "ok"
    assert measured == {"sound": 1, "flags": 1}


def test_the_backlog_is_most_played_first_and_skips_the_measured(db_session_factory, admin, monkeypatch):
    from app.models.track_user_stats import TrackUserStats
    from app.models.user import User
    from app.services import audio_analysis, audio_features, track_flags

    monkeypatch.setattr(audio_features, "profiler_available", lambda: True)
    monkeypatch.setattr(track_flags, "flags_available", lambda: True)
    monkeypatch.setattr(audio_analysis, "analysis_settings", lambda: (True, "03:30", "base"))
    monkeypatch.setattr(audio_analysis, "_ensure_worker", lambda budget_seconds=None: None)
    with audio_analysis._guard:
        audio_analysis._queue.clear()
        audio_analysis._queued.clear()

    popular = _track(db_session_factory, "backlog-popular")
    quiet = _track(db_session_factory, "backlog-quiet")
    db = db_session_factory()
    try:
        user_id = db.query(User.id).filter(User.username == "admin").scalar()
        db.add(TrackUserStats(user_id=user_id, track_id=popular, play_count=50))
        db.commit()
    finally:
        db.close()

    added = audio_analysis.enqueue_backlog(limit=10000, budget_seconds=None)
    assert added >= 2
    order = list(audio_analysis._queue)
    assert order.index(popular) < order.index(quiet)

    coverage_before = None
    db = db_session_factory()
    try:
        coverage_before = audio_analysis.coverage(db)
    finally:
        db.close()
    assert coverage_before["tracks"] >= 2
    with audio_analysis._guard:
        audio_analysis._queue.clear()
        audio_analysis._queued.clear()


def test_analysis_is_on_by_default_at_half_past_three():
    from app.services import audio_analysis

    enabled, at, model = audio_analysis.analysis_settings()
    assert enabled is True
    assert at == "03:30"
    assert model in ("base", "small")


# ------------------------------------------------------------- the routes


def test_status_flags_and_filters_over_the_api(admin, db_session_factory):
    track_id = _track(db_session_factory, "api-track", artist="Api Artist")

    status = admin.get("/api/audio/status")
    assert status.status_code == 200
    body = status.json()
    assert {"tracks", "profiled", "flagged", "vocal", "instrumental", "languages", "explicit", "analysis"} <= set(body)
    assert body["analysis"]["enabled"] is True

    # Words with a rude one in them: explicit, detected, vocal.
    put = admin.put(f"/api/tracks/{track_id}/lyrics", json={"plain": "oh shit here we go again\nsecond line"})
    assert put.status_code == 200
    assert put.json()["flags"]["explicit_state"] == "explicit"
    assert admin.get(f"/api/tracks/{track_id}/lyrics").json()["flags"]["vocal_state"] == "vocal"
    assert admin.get(f"/api/tracks/{track_id}").json()["explicit_state"] == "explicit"

    # The admin says otherwise, and the server keeps their word.
    flagged = admin.put(f"/api/tracks/{track_id}/flags", json={"explicit_state": "clean", "vocal_state": "instrumental", "language": "EN"})
    assert flagged.status_code == 200
    assert flagged.json() == {"vocal_state": "instrumental", "language": "en", "language_confidence": 1.0, "explicit_state": "clean", "set_by": "admin"}
    listed = admin.get("/api/tracks", params={"vocal_state": "instrumental", "limit": 500})
    assert track_id in {item["id"] for item in listed.json()["items"]}
    clean = admin.get("/api/tracks", params={"explicit_state": "clean", "limit": 500})
    assert track_id in {item["id"] for item in clean.json()["items"]}
    assert admin.put(f"/api/tracks/{track_id}/flags", json={"vocal_state": "humming"}).status_code == 422
    assert admin.put(f"/api/tracks/{track_id}/flags", json={}).status_code == 422

    reset = admin.delete(f"/api/tracks/{track_id}/flags")
    assert reset.status_code == 200
    assert reset.json()["set_by"] is None and reset.json()["vocal_state"] is None

    settings = admin.get("/api/settings").json()
    assert settings["audio_analysis_enabled"] is True and settings["audio_analysis_time"] == "03:30"
    settings.pop("lastfm_api_secret_set", None)
    settings.pop("lastfm_session_key_set", None)
    off = admin.put("/api/settings", json={**settings, "audio_analysis_enabled": False, "audio_analysis_time": "04:15"}).json()
    assert off["audio_analysis_enabled"] is False and off["audio_analysis_time"] == "04:15"
    assert admin.post("/api/audio/analyse").status_code == 409
    back = admin.put("/api/settings", json={**settings, "audio_analysis_enabled": True, "audio_analysis_time": ""}).json()
    assert back["audio_analysis_enabled"] is True and back["audio_analysis_time"] == "03:30"
