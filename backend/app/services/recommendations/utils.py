from app.models.track import Track
from app.schemas.track import TrackResponse


def build_track_response(track: Track) -> TrackResponse:
    return TrackResponse(
        id=track.id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        genre=track.genre,
        genres=[item.genre for item in track.track_genres if item.genre],
        file_path=track.file_path,
        raw_title=track.raw_title,
        raw_artist=track.raw_artist,
        raw_album=track.raw_album,
        raw_genre=track.raw_genre,
        musicbrainz_recording_id=track.musicbrainz_recording_id,
        lastfm_tags_enriched=track.lastfm_tags_enriched,
        artists=[item.artist_name for item in track.track_artists if item.artist_name],
    )