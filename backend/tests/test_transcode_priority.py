"""The track being played always gets CPU: slot priority, the HLS lead rule,
the ffmpeg timeout and the master playlist's rungs.

The field report: a phone tapped a track (HLS build, slot 1), asked two
seconds later for the next track's cache (slot 2), the starving player tried
the other variant (no slot, refused), and the music stopped at 28 seconds
with a spinner. These pin down each piece of the fix."""

import threading
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routes import tracks as t


@pytest.fixture
def quick_waits(monkeypatch):
    monkeypatch.setattr(t, "TRANSCODE_WAIT_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr("app.services.stream_cache_maintenance.has_room_for_transcode", lambda: True)


def _hold(slot_kwargs, release_event, acquired_event):
    def run():
        with t.transcode_slot("held", **slot_kwargs):
            acquired_event.set()
            release_event.wait(timeout=5)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert acquired_event.wait(timeout=2)
    return thread


def test_foreground_work_gets_a_slot_while_the_pool_is_full(quick_waits):
    release = threading.Event()
    holders = [_hold({}, release, threading.Event()) for _ in range(t.TRANSCODE_CONCURRENCY)]
    try:
        # Background: the pool is full, so it is refused after the wait.
        with pytest.raises(HTTPException) as refused:
            with t.transcode_slot("warm-up"):
                pass
        assert refused.value.status_code == 503

        # Foreground: the reserved slot is free, so it runs at once.
        started = time.monotonic()
        with t.transcode_slot("the playing track", foreground=True):
            assert time.monotonic() - started < 0.15
    finally:
        release.set()
        for h in holders:
            h.join(timeout=2)


def test_background_work_never_takes_the_reserved_slot(quick_waits):
    release = threading.Event()
    holders = [_hold({}, release, threading.Event()) for _ in range(t.TRANSCODE_CONCURRENCY)]
    try:
        with pytest.raises(HTTPException):
            with t.transcode_slot("warm-up", foreground=False):
                pass
        # Proof the reserved slot was untouched: foreground still gets it.
        with t.transcode_slot("playing", foreground=True):
            pass
    finally:
        release.set()
        for h in holders:
            h.join(timeout=2)


def test_a_second_foreground_build_falls_back_to_the_pool(quick_waits):
    release = threading.Event()
    first = _hold({"foreground": True}, release, threading.Event())
    try:
        # The reserved slot is held by the first foreground build; the pool is
        # free, so the second foreground build runs there rather than waiting.
        started = time.monotonic()
        with t.transcode_slot("variant switch", foreground=True):
            assert time.monotonic() - started < 0.15
    finally:
        release.set()
        first.join(timeout=2)


def test_the_ffmpeg_timeout_scales_with_the_track():
    assert t.ffmpeg_timeout_for(None) == t.FFMPEG_TIMEOUT_SECONDS
    assert t.ffmpeg_timeout_for(30) == t.FFMPEG_TIMEOUT_SECONDS
    assert t.ffmpeg_timeout_for(600) == 1260
    assert t.ffmpeg_timeout_for("bad") == t.FFMPEG_TIMEOUT_SECONDS


def test_the_master_playlist_lists_only_rungs_that_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "HLS_CACHE_ROOT", tmp_path)
    # The requested rung is always listed, built or not.
    assert t.hls_variant_listable(7, "aac_320", "fp", "aac_320")
    # Another rung is not, until its playlist is complete.
    assert not t.hls_variant_listable(7, "aac_128", "fp", "aac_320")
    paths = t.get_hls_cache_paths(7, "aac_128", "fp")
    paths["track_dir"].mkdir(parents=True)
    paths["playlist_path"].write_text("#EXTM3U\n#EXTINF:4,\nsegment_00000.ts\n")
    assert not t.hls_variant_listable(7, "aac_128", "fp", "aac_320")
    paths["playlist_path"].write_text("#EXTM3U\n#EXTINF:4,\nsegment_00000.ts\n#EXT-X-ENDLIST\n")
    assert t.hls_variant_listable(7, "aac_128", "fp", "aac_320")


def test_a_growing_playlist_tells_the_player_to_start_at_zero():
    text = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n#EXT-X-PLAYLIST-TYPE:EVENT\n#EXTINF:4.0,\nsegment_00000.ts\n#EXTINF:4.0,\n/abs/dir/segment_00001.ts\n"
    url = lambda name: f"/s/{name}?token=t"
    growing = t.render_variant_playlist(text, complete=False, segment_url=url)
    assert "#EXT-X-START:TIME-OFFSET=0,PRECISE=YES" in growing
    assert "#EXT-X-VERSION:6" in growing and "#EXT-X-VERSION:3" not in growing
    assert growing[-1] == "/s/segment_00001.ts?token=t"
    done = t.render_variant_playlist(text + "#EXT-X-ENDLIST\n", complete=True, segment_url=url)
    assert not any(line.startswith("#EXT-X-START") for line in done)
    assert "#EXT-X-VERSION:3" in done
