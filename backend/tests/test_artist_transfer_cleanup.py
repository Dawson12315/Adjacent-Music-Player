"""A transferred artist is retired, picture and all.

There is no artist table: an artist is a name on tracks and credits, plus a
picture row (and file) and Last.fm similarity rows keyed by that name. A
transfer moved the songs and left the rest behind; so did deleting an
artist's last track. Now a transfer retires the source — the target
inherits the picture if it has none — a rename re-keys both, and the
cleanup job retires whoever lost their last track.
"""

import os

import pytest

from app.models.artist_artwork import ArtistArtwork
from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.services.artist_identity import (
    ARTIST_ARTWORK_DIR,
    carry_artist_over,
    rekey_artist,
    retire_artist,
    retire_orphan_artists,
)
from app.utils.artist_normalization import normalize_artist_name
from tests.test_pass_p import _admin, _make_track


def _picture(db, name, filename):
    os.makedirs(ARTIST_ARTWORK_DIR, exist_ok=True)
    path = os.path.join(ARTIST_ARTWORK_DIR, filename)
    with open(path, "wb") as handle:
        handle.write(b"not really a jpeg")
    db.add(ArtistArtwork(artist_name=name, artist_key=normalize_artist_name(name), artwork_path=f"/uploads/artists/{filename}"))
    return path


def _similar(db, source, similar):
    db.add(
        ArtistLastfmSimilarity(
            source_artist_name=source, source_artist_key=normalize_artist_name(source),
            similar_artist_name=similar, similar_artist_key=normalize_artist_name(similar), match_score=0.5,
        )
    )


def _credit(db, track_id, name):
    db.add(TrackArtist(track_id=track_id, artist_name=name, position=0))


@pytest.fixture
def cast(client, db_session_factory):
    """Two artists with songs, a picture each, and similarity rows between them and a third."""
    _admin(client)
    old = _make_track(db_session_factory, "/lib/retire-old-1.flac", title="One", artist="Old Name", album="Early")
    old2 = _make_track(db_session_factory, "/lib/retire-old-2.flac", title="Two", artist="Old Name", album="Early")
    new = _make_track(db_session_factory, "/lib/retire-new-1.flac", title="Three", artist="New Name", album="Later")

    db = db_session_factory()
    try:
        for track_id, name in ((old, "Old Name"), (old2, "Old Name"), (new, "New Name")):
            _credit(db, track_id, name)
        old_file = _picture(db, "Old Name", "retire-old.jpg")
        _similar(db, "Old Name", "Someone Else")
        _similar(db, "Someone Else", "Old Name")
        _similar(db, "New Name", "Someone Else")
        db.commit()
    finally:
        db.close()

    yield {"old": [old, old2], "new": [new], "old_file": old_file}

    db = db_session_factory()
    try:
        ids = [old, old2, new]
        db.query(TrackArtist).filter(TrackArtist.track_id.in_(ids)).delete(synchronize_session=False)
        db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
        for name in ("Old Name", "New Name", "Someone Else", "Fresh Name"):
            key = normalize_artist_name(name)
            db.query(ArtistArtwork).filter(ArtistArtwork.artist_key == key).delete(synchronize_session=False)
            db.query(ArtistLastfmSimilarity).filter(
                (ArtistLastfmSimilarity.source_artist_key == key) | (ArtistLastfmSimilarity.similar_artist_key == key)
            ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    for leftover in ("retire-old.jpg", "retire-new.jpg"):
        path = os.path.join(ARTIST_ARTWORK_DIR, leftover)
        if os.path.exists(path):
            os.remove(path)


def _rows(db_session_factory, name):
    key = normalize_artist_name(name)
    db = db_session_factory()
    try:
        return {
            "artwork": db.query(ArtistArtwork).filter(ArtistArtwork.artist_key == key).first(),
            "similar": db.query(ArtistLastfmSimilarity)
            .filter((ArtistLastfmSimilarity.source_artist_key == key) | (ArtistLastfmSimilarity.similar_artist_key == key))
            .count(),
            "tracks": db.query(Track).filter(Track.artist == name).count(),
        }
    finally:
        db.close()


def test_a_transfer_retires_the_source_and_the_target_inherits_the_picture(client, cast, db_session_factory):
    response = client.patch(
        "/api/artists/transfer", json={"source_artist": "Old Name", "target_artist": "New Name"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["moved_tracks"] == 2
    assert body["retired"] == {"artwork": False, "similarity_rows": 2, "artwork_carried": True}

    old = _rows(db_session_factory, "Old Name")
    new = _rows(db_session_factory, "New Name")
    assert old["tracks"] == 0 and old["artwork"] is None and old["similar"] == 0
    # The picture moved rather than being deleted: the target had none.
    assert new["artwork"] is not None and new["artwork"].artwork_path == "/uploads/artists/retire-old.jpg"
    assert new["artwork"].artist_name == "New Name"
    assert os.path.exists(cast["old_file"])
    assert new["tracks"] == 3


def test_a_target_with_its_own_picture_keeps_it_and_the_source_file_goes(client, cast, db_session_factory):
    db = db_session_factory()
    try:
        new_file = _picture(db, "New Name", "retire-new.jpg")
        db.commit()
    finally:
        db.close()

    response = client.patch(
        "/api/artists/transfer", json={"source_artist": "Old Name", "target_artist": "New Name"}
    )

    assert response.status_code == 200
    assert response.json()["retired"] == {"artwork": True, "similarity_rows": 2, "artwork_carried": False}
    assert not os.path.exists(cast["old_file"])
    assert os.path.exists(new_file)
    assert _rows(db_session_factory, "New Name")["artwork"].artwork_path == "/uploads/artists/retire-new.jpg"


def test_a_rename_carries_the_picture_and_the_similarity_rows(client, cast, db_session_factory):
    response = client.patch(
        "/api/artists/rename", json={"current_artist": "Old Name", "new_artist": "Fresh Name"}
    )

    assert response.status_code == 200
    assert response.json()["artwork_moved"] is True
    assert response.json()["similarity_rows_moved"] == 2

    old = _rows(db_session_factory, "Old Name")
    fresh = _rows(db_session_factory, "Fresh Name")
    assert old["artwork"] is None and old["similar"] == 0
    assert fresh["artwork"].artist_name == "Fresh Name"
    assert fresh["similar"] == 2
    assert fresh["tracks"] == 2
    assert os.path.exists(cast["old_file"])


def test_the_cleanup_retires_an_artist_whose_last_track_went(client, cast, db_session_factory):
    # Delete the tracks the way the cleanup does, then ask it to tidy.
    db = db_session_factory()
    try:
        db.query(TrackArtist).filter(TrackArtist.track_id.in_(cast["old"])).delete(synchronize_session=False)
        db.query(Track).filter(Track.id.in_(cast["old"])).delete(synchronize_session=False)
        db.commit()
        retired = retire_orphan_artists(db)
        db.commit()
    finally:
        db.close()

    assert retired["artists_retired"] == 1
    # Old Name's own row goes, and Someone Else's (no tracks either); New
    # Name's row pointing at Someone Else stays — a neighbour outside the
    # library is exactly what the retriever reads.
    assert retired["similarity_rows"] == 2
    assert _rows(db_session_factory, "Old Name")["artwork"] is None
    assert _rows(db_session_factory, "New Name")["similar"] == 1
    assert not os.path.exists(cast["old_file"])


def test_the_service_refuses_nonsense_quietly(db_session_factory):
    db = db_session_factory()
    try:
        assert retire_artist(db, "") == {"artwork": False, "similarity_rows": 0}
        assert carry_artist_over(db, "Same", "same") == {"artwork": False, "similarity_rows": 0, "artwork_carried": False}
        assert rekey_artist(db, "", "X") == {"artwork_moved": False, "similarity_rows_moved": 0}
    finally:
        db.close()
