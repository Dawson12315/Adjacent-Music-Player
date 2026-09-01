import { useCallback } from "react";
import { Link } from "react-router-dom";

import { getGreeting, useHomeData } from "./useHomeData";
import { Artwork } from "../../components/Artwork";
import { DuckMark } from "../../components/DuckMark";
import { Icon } from "../../components/Icon";
import { CardGridSkeleton } from "../library/TrackListSkeleton";
import { useAuth } from "../../contexts/AuthContext";
import { useLibrary } from "../../contexts/LibraryContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { buildGenrePath, buildPlaylistPath } from "../../hooks/useNavigation";
import { resolveAlbumArtwork, resolvePlaylistArtwork } from "../../utils/artwork";

/**
 * The landing surface.
 *
 * There was no home page at all before — "/" was the raw track list, all 36,534 rows,
 * page one of 731. The listening data shows what that cost: 95% of plays started from
 * "library" browsing and only 4.6% from a playlist, because nothing surfaced anything.
 */
export function HomeView() {
  const { currentUser } = useAuth();
  const { playlists, albumArtworkMap, artists, albums, trackCount } = useLibrary();
  const { playTrack } = usePlayer();
  const home = useHomeData();

  const playFrom = useCallback(
    (track, list, sourceType) => {
      playTrack(track, list, { source_type: sourceType, source_id: null });
    },
    [playTrack],
  );

  const artworkFor = useCallback(
    (track) => resolveAlbumArtwork(track.album, albumArtworkMap),
    [albumArtworkMap],
  );

  return (
    <div className="home">
      <div className="home__greeting">
        <DuckMark tile className="home__greeting-mark" />
        <div className="home__greeting-text">
          <h1>{getGreeting()}</h1>
          <p>
            {currentUser?.username ? `Welcome back, ${currentUser.username}.` : "Welcome back."}{" "}
            {trackCount > 0 && `${trackCount.toLocaleString()} tracks waiting.`}
          </p>
        </div>
      </div>

      {/* Quick access: the six most recent things, as wide tiles */}
      {home.recentlyPlayed.length > 0 && (
        <div className="home__quick">
          {home.recentlyPlayed.slice(0, 6).map((track) => (
            <button
              key={`quick-${track.id}`}
              className="quick-tile"
              type="button"
              onClick={() => playFrom(track, home.recentlyPlayed, "library")}
            >
              <Artwork
                artwork={artworkFor(track)}
                className="quick-tile__art"
                size={52}
              />
              <span className="quick-tile__body">
                <span className="quick-tile__name">{track.title}</span>
                <span className="quick-tile__meta">{track.artist || "Unknown Artist"}</span>
              </span>
            </button>
          ))}
        </div>
      )}

      <Rail
        title="For you"
        subtitle="Built from what you actually play"
        icon="sparkle"
        isLoading={home.isLoadingForYou}
        tracks={home.forYou}
        artworkFor={artworkFor}
        onPlay={(track) => playFrom(track, home.forYou, "recommendation")}
        action={
          <button
            className="btn btn--icon btn--ghost"
            type="button"
            aria-label="Refresh recommendations"
            title="Refresh recommendations"
            onClick={home.refreshForYou}
            disabled={home.isLoadingForYou}
          >
            <Icon name="refresh" size={15} />
          </button>
        }
      />

      <Rail
        title="Jump back in"
        icon="clock"
        isLoading={home.isLoading}
        tracks={home.recentlyPlayed}
        artworkFor={artworkFor}
        onPlay={(track) => playFrom(track, home.recentlyPlayed, "library")}
      />

      <Rail
        title="On repeat"
        subtitle="Your most played"
        icon="repeat"
        isLoading={home.isLoading}
        tracks={home.topPlayed}
        artworkFor={artworkFor}
        onPlay={(track) => playFrom(track, home.topPlayed, "library")}
        showCount
      />

      {playlists.length > 0 && (
        <section className="rail">
          <div className="section-head">
            <h2 className="section-head__title">Your playlists</h2>
          </div>

          <div className="rail__scroller scroll-x">
            {playlists.map((playlist) => (
              <Link
                key={playlist.id}
                to={buildPlaylistPath(playlist.id)}
                className="entity-card"
              >
                <Artwork
                  artwork={resolvePlaylistArtwork(playlist)}
                  className="entity-card__art"
                  size={168}
                />
                <span className="entity-card__body">
                  <span className="entity-card__name">{playlist.name}</span>
                  <span className="entity-card__meta">
                    {playlist.is_system ? "System playlist" : "Playlist"}
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {home.topGenres.length > 0 && (
        <section className="rail">
          <div className="section-head">
            <h2 className="section-head__title">Genres you play</h2>
            <Link className="section-head__link" to="/genres">
              All genres
            </Link>
          </div>

          <div className="genre-grid">
            {home.topGenres.slice(0, 8).map((genre, index) => (
              <Link
                key={genre.name}
                to={buildGenrePath(genre.name)}
                className={`genre-card genre-card--${(index % 10) + 1}`}
              >
                <span className="genre-card__rank">#{index + 1}</span>
                <span className="genre-card__title">{genre.name}</span>
                <span className="genre-card__meta">{genre.play_count} plays</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <div className="home__library-strip">
        <Link to="/tracks" className="home__library-stat">
          <span className="home__library-stat-value">{trackCount.toLocaleString()}</span>
          <span className="home__library-stat-label">tracks</span>
        </Link>
        <Link to="/artists" className="home__library-stat">
          <span className="home__library-stat-value">{artists.length.toLocaleString()}</span>
          <span className="home__library-stat-label">artists</span>
        </Link>
        <Link to="/albums" className="home__library-stat">
          <span className="home__library-stat-value">{albums.length.toLocaleString()}</span>
          <span className="home__library-stat-label">albums</span>
        </Link>
        <Link to="/insights" className="home__library-stat">
          <span className="home__library-stat-value">
            <Icon name="insights" size={20} />
          </span>
          <span className="home__library-stat-label">insights</span>
        </Link>
      </div>
    </div>
  );
}

/** A horizontal shelf of track cards. */
function Rail({ title, subtitle, icon, tracks, isLoading, artworkFor, onPlay, showCount, action }) {
  if (!isLoading && tracks.length === 0) {
    return null;
  }

  return (
    <section className="rail">
      <div className="section-head">
        <h2 className="section-head__title">
          {icon && <Icon name={icon} size={16} />} {title}
        </h2>
        {subtitle && <span className="section-head__link">{subtitle}</span>}
        {action}
      </div>

      {isLoading ? (
        <CardGridSkeleton count={6} className="rail__scroller" />
      ) : (
        <div className="rail__scroller scroll-x">
          {tracks.map((track) => (
            <button
              key={track.id}
              className="entity-card"
              type="button"
              onClick={() => onPlay(track)}
            >
              <Artwork
                artwork={artworkFor(track)}
                className="entity-card__art"
                size={168}
              />
              <span className="entity-card__body">
                <span className="entity-card__name">{track.title}</span>
                <span className="entity-card__meta">
                  {showCount && track.play_count
                    ? `${track.play_count} plays`
                    : track.artist || "Unknown Artist"}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
