"""A record is filed under its album artist when the file names one.

A compilation with a performer per track used to be one album per
performer; artwork set on the album page landed on one of them. The
album-artist tag now groups the record, and everything that keys artwork
by a record's artist uses the same answer.
"""

import shutil
from pathlib import Path

import pytest

from app.services.track_resolution import resolve_track_fields
from app.services.track_responses import record_artist
from tests.test_pass_p import _admin, _make_track

FIXTURES = Path(__file__).parent / "fixtures" / "audio"


class _Row:
    def __init__(self, artist, album_artist):
        self.artist, self.album_artist = artist, album_artist


def test_the_record_artist_is_the_album_artist_when_there_is_one():
    assert record_artist(_Row("Hans Zimmer", "Various Artists")) == "Various Artists"
    assert record_artist(_Row("Hans Zimmer", "")) == "Hans Zimmer"
    assert record_artist(_Row("Hans Zimmer", None)) == "Hans Zimmer"
    assert record_artist(_Row(None, None)) is None


def test_the_resolver_carries_the_album_artist_tag_only():
    fields = resolve_track_fields({"title": "T", "artist": "Performer", "album_artist": "Various Artists", "album": "Mix"}, "/m/a/01 - T.flac")
    assert fields["album_artist"] == "Various Artists"
    fields = resolve_track_fields({"title": "T", "artist": "Performer", "album": "Solo"}, "/m/a/01 - T.flac")
    assert fields["album_artist"] is None, "a normal album groups on the track artist"


@pytest.fixture(scope="module")
def compilation(client, db_session_factory):
    _admin(client)
    ids = []
    for index, (artist, album_artist) in enumerate(
        [("Perf One", "Various Artists"), ("Perf Two", "Various Artists"), ("Perf Three", "Various Artists"), ("Perf Four", None)]
    ):
        ids.append(
            _make_track(
                db_session_factory,
                f"/lib/comp-{index}.flac",
                title=f"Comp {index}",
                artist=artist,
                album="Now That Is Music",
                album_artist=album_artist,
                track_number=index + 1,
            )
        )
    yield ids
    from app.models.track import Track

    db = db_session_factory()
    try:
        db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_a_compilation_is_one_album_plus_the_untagged_straggler(client, compilation):
    albums = [a for a in client.get("/api/albums", params={"detailed": 1}).json() if a["name"] == "Now That Is Music"]
    by_artist = {a["artist"]: a["track_count"] for a in albums}
    # Three performers with the album-artist tag are one record; the file
    # without the tag groups on its own artist, as it always did.
    assert by_artist == {"Various Artists": 3, "Perf Four": 1}

    mobile = [a for a in client.get("/api/mobile/albums").json() if a["name"] == "Now That Is Music"]
    assert {a["artist"]: a["trackCount"] for a in mobile} == {"Various Artists": 3, "Perf Four": 1}


def test_the_album_page_opens_the_whole_record(client, compilation):
    rows = client.get("/api/albums/Now That Is Music/tracks", params={"artist": "Various Artists"}).json()
    items = rows if isinstance(rows, list) else rows["items"]
    assert [row["artist"] for row in items] == ["Perf One", "Perf Two", "Perf Three"]
    assert {row["album_artist"] for row in items} == {"Various Artists"}
    # The straggler reports its own artist as the record's.
    other = client.get("/api/albums/Now That Is Music/tracks", params={"artist": "Perf Four"}).json()
    other = other if isinstance(other, list) else other["items"]
    assert [row["album_artist"] for row in other] == ["Perf Four"]


def test_artwork_set_on_the_record_shows_on_every_track(client, compilation):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 13 + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    upload = client.post(
        "/api/albums/Now That Is Music/artwork",
        params={"artist": "Various Artists"},
        files={"file": ("cover.png", png, "image/png")},
    )
    assert upload.status_code in (200, 201), upload.text
    rows = client.get("/api/albums/Now That Is Music/tracks", params={"artist": "Various Artists"}).json()
    items = rows if isinstance(rows, list) else rows["items"]
    paths = {row["album_artwork_path"] for row in items}
    assert len(paths) == 1 and None not in paths, "one picture, on all three performers' tracks"


def test_the_scanner_stores_the_album_artist_and_reads_it_once_for_old_rows(client, db_session_factory, tmp_path, monkeypatch):
    from app.models.track import Track
    from app.services import scanner

    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)
    library = tmp_path / "aa"
    library.mkdir()
    tagged = library / "Various Artists - Mix - 01 - A.m4a"
    plain = library / "Solo - Record - 01 - B.flac"
    shutil.copy(FIXTURES / "tagged.m4a", tagged)        # album artist "Various Artists"
    shutil.copy(FIXTURES / "untagged.flac", plain)

    # One row imported before the column existed: album_artist NULL.
    stat = plain.stat()
    db = db_session_factory()
    try:
        db.add(Track(title="B", artist="Solo", album="Record", raw_artist="Solo", file_path=str(plain), file_size=stat.st_size, file_mtime_ns=stat.st_mtime_ns, track_number=1, album_artist=None))
        db.commit()
    finally:
        db.close()

    assert scanner.scan_directory(str(library), limit=10)["added"] == 1

    db = db_session_factory()
    try:
        assert db.query(Track).filter(Track.file_path == str(tagged)).one().album_artist == "Various Artists"
        # Read once: the file has no tag, so the row now says "" rather than NULL.
        assert db.query(Track).filter(Track.file_path == str(plain)).one().album_artist == ""
    finally:
        # Rows whose files exist would make the maintenance tests' "none of
        # our files are here" case untrue; leave the shared database as found.
        db.query(Track).filter(Track.file_path.like(f"{library}%")).delete(synchronize_session=False)
        db.commit()
        db.close()
