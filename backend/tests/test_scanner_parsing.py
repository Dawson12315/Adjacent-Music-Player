"""The scanner's reading of tags, names and folders (15 Oct 2026 audit).

The fixtures under tests/fixtures/audio are 0.2 s of sine wave in every
supported container, tagged the same way, so one table drives every format.
"""

import os
import shutil
from pathlib import Path

import pytest

from app.services.filename_metadata import (
    clean_folder_name,
    extract_metadata_from_filename,
    extract_metadata_from_folders,
    extract_track_number_from_filename,
    parse_filename,
)
from app.services.metadata import extract_track_metadata
from app.services.metadata_normalizer import (
    normalize_album,
    normalize_artist_list,
    normalize_artist_name,
    normalize_title,
)
from app.services.scanner import is_excluded_path
from app.services.track_resolution import resolve_track_fields

FIXTURES = Path(__file__).parent / "fixtures" / "audio"


# --- Tags: every container reads the same ----------------------------------


@pytest.mark.parametrize("extension", ["mp3", "flac", "m4a", "ogg", "opus", "wav"])
def test_every_container_yields_the_same_tags(extension):
    metadata = extract_track_metadata(str(FIXTURES / f"tagged.{extension}"))
    assert metadata["title"] == "Southern Messiah"
    assert metadata["artist"].startswith("Hans Zimmer")
    assert metadata["album_artist"] == "Various Artists"
    assert metadata["album"] == "Dune Part Two"
    assert metadata["track_number"] == 7
    assert metadata["disc_number"] == 2
    assert "Soundtrack" in metadata["genre"]
    assert metadata["duration_seconds"] and metadata["duration_seconds"] > 0.1


@pytest.mark.parametrize("extension", ["mp3", "flac", "m4a", "ogg", "opus", "wav"])
def test_an_untagged_file_reports_nothing_not_its_filename(extension):
    metadata = extract_track_metadata(str(FIXTURES / f"untagged.{extension}"))
    assert metadata["title"] is None
    assert metadata["artist"] is None
    assert metadata["album"] is None
    assert metadata["track_number"] is None


def test_multi_valued_frames_are_joined_not_nul_separated():
    # Picard-style: two TPE1 values, two TCON values, one a numeric ID3 code.
    metadata = extract_track_metadata(str(FIXTURES / "multivalue.mp3"))
    assert metadata["artist"] == "Kodak Black; 1900Rugrat"
    assert metadata["genre"] == "Hip-Hop; Trap"
    assert "\x00" not in metadata["artist"]

    wav = extract_track_metadata(str(FIXTURES / "tagged.wav"))
    assert wav["artist"] == "Hans Zimmer; Loire Cotler"
    assert wav["genre"] == "Rock; Soundtrack", "the (17) code became a name"


# --- Names -------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Kodak Black - Kodak The Blessing - 15 - Idols Turn Into Rivals.flac", ("Kodak Black", "Kodak The Blessing", "Idols Turn Into Rivals", 15, None)),
        ("07 - Southern Messiah.flac", (None, None, "Southern Messiah", 7, None)),
        ("Artist - 05 - Title.mp3", ("Artist", None, "Title", 5, None)),
        ("Artist - Album - 1-07 - Title.flac", ("Artist", "Album", "Title", 7, 1)),
        ("orion sun - A Collection - 04 - Space Jam - An Odyssey.flac", ("orion sun", "A Collection", "Space Jam - An Odyssey", 4, None)),
        ("Some Artist - Some Song.mp3", ("Some Artist", None, "Some Song", None, None)),
        ("Band - 2019 - Song.mp3", ("Band", None, "Song", None, None)),
        ("112 - Cupid.mp3", ("112", None, "Cupid", None, None)),
        ("03 Blue Harbour.mp3", (None, None, "Blue Harbour", 3, None)),
        ("03. Blue Harbour.mp3", (None, None, "Blue Harbour", 3, None)),
        ("01_Title.flac", (None, None, "Title", 1, None)),
        ("1-07 Title.flac", (None, None, "Title", 7, 1)),
        ("7 Rings.mp3", (None, None, "7 Rings", 7, None)),
        ("22.mp3", (None, None, "22", None, None)),
        ("1979.mp3", (None, None, "1979", None, None)),
        ("Loose Track.mp3", (None, None, "Loose Track", None, None)),
    ],
)
def test_the_name_parser(name, expected):
    parsed = parse_filename(f"/m/a/{name}")
    assert (parsed.artist, parsed.album, parsed.title, parsed.track_number, parsed.disc_number) == expected


def test_the_old_name_functions_still_agree():
    name = "/m/Kodak Black/Kodak The Blessing (2026)/Kodak Black - Kodak The Blessing - 15 - Idols Turn Into Rivals.flac"
    assert extract_metadata_from_filename(name) == ("Kodak Black", "Kodak The Blessing", "Idols Turn Into Rivals")
    assert extract_track_number_from_filename(name) == 15
    assert extract_metadata_from_filename("/m/Loose Track.mp3") == (None, None, "Loose Track")


# --- Folders -----------------------------------------------------------------


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/m/Hans Zimmer/Dune - Part Two - Original Motion Picture Soundtrack (2024)/Disc/07 - X.flac", ("Hans Zimmer", "Dune - Part Two - Original Motion Picture Soundtrack")),
        ("/m/Hans Zimmer/Dune (2024) [FLAC 24bit]/CD 2/07 - X.flac", ("Hans Zimmer", "Dune")),
        ("/m/Pet Shop Boys/Pet Shop Boys - The Most Incredible Thing [2011]/01 - X.flac", ("Pet Shop Boys", "The Most Incredible Thing")),
        ("/m/Britney Spears/Me Against the Music (2003)/12 Vinyl 01/x.flac", ("Britney Spears", "Me Against the Music")),
        ("/m/Music/x.flac", (None, None)),
        ("/m/x.flac", (None, None)),
        ("/m/Various/Soundtracks/Dune (2024)/x.flac", (None, "Dune")),
    ],
)
def test_the_folder_parser(path, expected):
    assert extract_metadata_from_folders(path, "/m") == expected


def test_folder_decorations():
    assert clean_folder_name("Trap-a-Thon (2007)") == "Trap-a-Thon"
    assert clean_folder_name("Album [2019] [FLAC]") == "Album"
    assert clean_folder_name("1989") == "1989"


# --- Resolution: tag, then name, then folders -------------------------------


def test_an_untagged_soundtrack_file_is_not_an_artist_called_07():
    path = "/m/Hans Zimmer/Dune - Part Two - Original Motion Picture Soundtrack (2024)/Disc/07 - Southern Messiah.flac"
    fields = resolve_track_fields({}, path, "/m")
    assert fields["artist"] == "Hans Zimmer"
    assert fields["artists"] == ["Hans Zimmer"]
    assert fields["album"] == "Dune - Part Two - Original Motion Picture Soundtrack"
    assert fields["title"] == "Southern Messiah"
    assert fields["track_number"] == 7
    assert fields["sources"] == {"title": "filename", "artist": "folder", "album": "folder"}


def test_the_album_artist_tag_stands_in_for_a_missing_artist():
    fields = resolve_track_fields(
        {"title": "The Wedding", "album": "The Most Incredible Thing", "album_artist": "Pet Shop Boys"},
        "/m/x/07 - The Wedding.flac",
        "/m",
    )
    assert fields["artist"] == "Pet Shop Boys"
    assert fields["album"] == "The Most Incredible Thing"
    assert fields["sources"]["artist"] == "album artist tag"


def test_a_tagged_file_is_untouched_by_the_fallbacks():
    fields = resolve_track_fields(
        {"title": "Aw-Man", "artist": "Gucci Mane", "album": "Trap-a-Thon", "track_number": 7},
        "/m/Other Artist/Other Album/Gucci Mane - Trap-a-Thon - 07 - Aw-Man.flac",
        "/m",
    )
    assert (fields["artist"], fields["album"], fields["title"], fields["track_number"]) == ("Gucci Mane", "Trap-a-Thon", "Aw-Man", 7)
    assert fields["sources"] == {"title": "tag", "artist": "tag", "album": "tag"}


def test_a_title_tag_that_is_just_the_filename_is_parsed_like_one():
    fields = resolve_track_fields({"title": "07 - Southern Messiah", "artist": "Hans Zimmer"}, "/m/a/07 - Southern Messiah.flac")
    assert fields["title"] == "Southern Messiah"
    fields = resolve_track_fields({"title": "Freddie Dredd & Jak3  - Dance RMX", "artist": "Freddie Dredd"}, "/m/a/05 - Dance RMX.flac")
    assert fields["title"] == "Dance RMX"


def test_a_real_dash_in_a_title_survives():
    fields = resolve_track_fields(
        {"title": "Space Jam - An Odyssey", "artist": "orion sun"},
        "/m/a/orion sun - A Collection - 04 - Space Jam - An Odyssey.flac",
    )
    assert fields["title"] == "Space Jam - An Odyssey"
    fields = resolve_track_fields(
        {"title": "Grace (Live at Palais Theatre, Melbourne, Australia - Feb 1996)", "artist": "Jeff Buckley"},
        "/m/a/Jeff Buckley - The Grace EP - 01 - Grace (live at Palais Theatre, Melbourne, Australia - Feb 1996).flac",
    )
    assert fields["title"] == "Grace (Live at Palais Theatre, Melbourne, Australia - Feb 1996)"


def test_multi_valued_credits_become_separate_credits():
    fields = resolve_track_fields({"title": "Nunchucks", "artist": "Kodak Black; 1900Rugrat"}, "/m/a/05 - Nunchucks.flac")
    assert fields["artist"] == "Kodak Black"
    assert fields["artists"] == ["Kodak Black", "1900Rugrat"]


# --- Normalising -------------------------------------------------------------


def test_feature_credits_leave_the_title_in_every_spelling():
    assert normalize_title("Problem (feat. Iggy Azalea)") == "Problem"
    assert normalize_title("Don't Mind If I Do (feat Ella Langley)") == "Don't Mind If I Do"
    assert normalize_title("GHOUL ft. Gizmo") == "GHOUL"
    assert normalize_title("Silent Night Feat. Boyz II Men") == "Silent Night"
    assert normalize_title("King For A Day (featuring Kellin Quinn)") == "King For A Day"
    assert normalize_title("Nat King Cole (Unlocked) feat. Lil Wayne") == "Nat King Cole (Unlocked)"
    assert normalize_title("Song feat. X (Remix)") == "Song (Remix)"
    assert normalize_title("feat. Nobody") == "feat. Nobody", "a title that is only a credit keeps its name"
    # Words that merely contain the letters are left alone.
    assert normalize_title("Soft Rock") == "Soft Rock"
    assert normalize_title("Lift Off") == "Lift Off"
    assert normalize_album("Wow. (Remix) (ft Roddy Ricch, Tyga)") == "Wow. (Remix)"


def test_lower_case_names_are_capitalised_without_mangling():
    assert normalize_artist_name("drake") == "Drake"
    assert normalize_artist_name("d4vd") == "D4vd"
    assert normalize_artist_name("MGMT") == "MGMT"
    assert normalize_artist_list("Bhad Bhabie & $hirak") == ["Bhad Bhabie", "$hirak"]


def test_bands_with_separators_in_their_names_stay_whole():
    assert normalize_artist_list("AC/DC") == ["AC/DC"]
    assert normalize_artist_list("Hootie & The Blowfish") == ["Hootie & The Blowfish"]
    assert normalize_artist_list("Maddie & Tae") == ["Maddie & Tae"]
    # Two acts are still two acts.
    assert normalize_artist_list("Post Malone & The Weeknd") == ["Post Malone", "The Weeknd"]
    assert normalize_artist_list("Riley Green/Jessi Alexander") == ["Riley Green", "Jessi Alexander"]


# --- The walk ----------------------------------------------------------------


def test_housekeeping_folders_and_resource_forks_are_skipped():
    assert is_excluded_path(("#recycle", "Album", "01 - Song.flac"))
    assert is_excluded_path(("Artist", "@eaDir", "x.flac"))
    assert is_excluded_path(("Artist", "Album", "._01 - Song.flac"))
    assert is_excluded_path((".Trash-1000", "files", "x.mp3"))
    assert not is_excluded_path(("Artist", "Album", "01 - Song.flac"))
    assert not is_excluded_path(("Artist", "Album (2024) [FLAC]", "01 - Song.flac"))


def _scan(library, monkeypatch):
    from app.services import scanner

    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)
    return scanner.scan_directory(str(library), limit=1000)


def test_the_scanner_imports_a_soundtrack_rip_under_its_composer(client, db_session_factory, tmp_path, monkeypatch):
    from app.models.track import Track
    from app.models.track_artist import TrackArtist

    library = tmp_path / "lib"
    album = library / "Hans Zimmer" / "Dune - Part Two - Original Motion Picture Soundtrack (2024)" / "Disc"
    album.mkdir(parents=True)
    shutil.copy(FIXTURES / "untagged.flac", album / "07 - Southern Messiah.flac")
    shutil.copy(FIXTURES / "untagged.flac", album / "08 - Ornithopter Attack.flac")

    # An .m4a the old reader could not read, in a folder that says nothing.
    other = library / "misc"
    other.mkdir()
    shutil.copy(FIXTURES / "tagged.m4a", other / "something.m4a")

    # Files that are not part of the library.
    (library / "#recycle").mkdir()
    shutil.copy(FIXTURES / "tagged.flac", library / "#recycle" / "deleted.flac")
    shutil.copy(FIXTURES / "tagged.flac", album / "._07 - Southern Messiah.flac")

    result = _scan(library, monkeypatch)
    assert result["added"] == 3

    db = db_session_factory()
    try:
        rows = {t.file_path.rsplit("/", 1)[-1]: t for t in db.query(Track).filter(Track.file_path.like(f"{library}%")).all()}
        assert set(rows) == {"07 - Southern Messiah.flac", "08 - Ornithopter Attack.flac", "something.m4a"}

        messiah = rows["07 - Southern Messiah.flac"]
        assert (messiah.title, messiah.artist, messiah.album, messiah.track_number) == (
            "Southern Messiah", "Hans Zimmer", "Dune - Part Two - Original Motion Picture Soundtrack", 7
        )
        assert messiah.raw_artist is None, "what the file said is kept apart from what was inferred"
        assert [c.artist_name for c in db.query(TrackArtist).filter(TrackArtist.track_id == messiah.id)] == ["Hans Zimmer"]

        m4a = rows["something.m4a"]
        assert (m4a.title, m4a.artist, m4a.album, m4a.track_number, m4a.disc_number) == ("Southern Messiah", "Hans Zimmer", "Dune Part Two", 7, 2)
        assert m4a.raw_artist == "Hans Zimmer"
    finally:
        db.close()


def test_the_next_scan_repairs_rows_the_old_reader_misread(client, db_session_factory, tmp_path, monkeypatch):
    from app.models.track import Track
    from app.models.track_artist import TrackArtist

    library = tmp_path / "lib2"
    album = library / "Hans Zimmer" / "Dune (2024)"
    album.mkdir(parents=True)
    numbered = album / "07 - Worm Ride.flac"
    shutil.copy(FIXTURES / "untagged.flac", numbered)
    m4a = library / "Walker Hayes" / "Reason to Rhyme (2013)" / "Walker Hayes - Reason to Rhyme - 01 - Pants.m4a"
    m4a.parent.mkdir(parents=True)
    shutil.copy(FIXTURES / "tagged.m4a", m4a)
    fine = album / "Hans Zimmer - Dune - 01 - Arrival.flac"
    shutil.copy(FIXTURES / "untagged.flac", fine)

    # Rows exactly as the old scanner left them.
    db = db_session_factory()
    try:
        for path, title, artist, album_name, raw_artist in (
            (numbered, "Worm Ride", "07", None, None),
            (m4a, "Pants", "Walker Hayes", "Reason to Rhyme", None),
            (fine, "Arrival", "Hans Zimmer", "Dune", None),
        ):
            stat = path.stat()
            track = Track(
                title=title, artist=artist, album=album_name, raw_artist=raw_artist,
                file_path=str(path), file_size=stat.st_size, file_mtime_ns=stat.st_mtime_ns, track_number=0,
            )
            db.add(track)
            db.flush()
            db.add(TrackArtist(track_id=track.id, artist_name=artist, position=0))
        db.commit()
        # A hand edit on a healthy row must survive the scan.
        healthy = db.query(Track).filter(Track.file_path == str(fine)).one()
        healthy.title = "Arrival (edited by hand)"
        db.commit()
    finally:
        db.close()

    result = _scan(library, monkeypatch)
    assert result["added"] == 0

    db = db_session_factory()
    try:
        worm = db.query(Track).filter(Track.file_path == str(numbered)).one()
        assert (worm.artist, worm.album, worm.title, worm.track_number) == ("Hans Zimmer", "Dune", "Worm Ride", 7)
        assert [c.artist_name for c in db.query(TrackArtist).filter(TrackArtist.track_id == worm.id)] == ["Hans Zimmer"]

        pants = db.query(Track).filter(Track.file_path == str(m4a)).one()
        assert (pants.title, pants.artist, pants.album, pants.raw_artist) == ("Southern Messiah", "Hans Zimmer", "Dune Part Two", "Hans Zimmer")

        untouched = db.query(Track).filter(Track.file_path == str(fine)).one()
        assert untouched.title == "Arrival (edited by hand)"
        assert untouched.artist == "Hans Zimmer"
    finally:
        db.close()
