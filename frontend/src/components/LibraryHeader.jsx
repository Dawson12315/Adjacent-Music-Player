import { useEffect, useMemo, useState } from "react";

import { EditArtistModal } from "../features/metadata/EditArtistModal";
import { useLibrary } from "../contexts/LibraryContext";
import { usePlayer } from "../contexts/PlayerContext";
import { useLibraryFilters } from "../features/library/useLibraryFilters";
import { useNavigation } from "../hooks/useNavigation";
import { getArtistArtwork, getArtistGenres } from "../services/artistsService";
import { artworkUrl } from "../config";
import { resolveAlbumArtwork } from "../utils/artwork";

/**
 * The page header: artist or album hero image, title, counts, play control, and the
 * artist actions menu.
 *
 * The artist's artwork and genres are fetched here, each with an AbortController so that
 * switching artists quickly cannot land an older response after a newer one.
 */
export function LibraryHeader() {
  const { tracks, playlists, playlistTracks, albumArtworkMap, loading, error } =
    useLibrary();
  const { playTracks } = usePlayer();
  const {
    activeView,
    selectedArtist,
    selectedAlbum,
    selectedGenre,
    selectedPlaylistId,
  } = useNavigation();
  const { visibleTracks } = useLibraryFilters();

  // Stored with the artist it describes, so switching artists clears the previous one by
  // derivation rather than by resetting state from an effect.
  const [artistData, setArtistData] = useState({ artist: null, artworkPath: "", genres: [] });
  const [isActionsOpen, setIsActionsOpen] = useState(false);
  const [isEditingArtist, setIsEditingArtist] = useState(false);

  const hasArtistData = Boolean(selectedArtist) && artistData.artist === selectedArtist;
  const artistArtworkPath = hasArtistData ? artistData.artworkPath : "";
  const artistGenres = hasArtistData ? artistData.genres : [];

  useEffect(() => {
    if (!selectedArtist) {
      return undefined;
    }

    const controller = new AbortController();

    Promise.all([
      getArtistArtwork(selectedArtist, { signal: controller.signal }),
      getArtistGenres(selectedArtist, { signal: controller.signal }),
    ])
      .then(([artwork, genres]) => {
        if (!controller.signal.aborted) {
          setArtistData({
            artist: selectedArtist,
            artworkPath: artwork.artwork_path || "",
            genres: genres || [],
          });
        }
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") {
          setArtistData({ artist: selectedArtist, artworkPath: "", genres: [] });
        }
      });

    return () => controller.abort();
  }, [selectedArtist]);

  const counts = useMemo(() => {
    if (selectedArtist) {
      const artistTracks = tracks.filter((track) => track.artist === selectedArtist);

      return {
        tracks: artistTracks.length,
        albums: new Set(artistTracks.map((track) => track.album).filter(Boolean)).size,
      };
    }

    if (selectedAlbum) {
      const albumTracks = tracks.filter((track) => track.album === selectedAlbum);

      return {
        tracks: albumTracks.length,
        artists: new Set(albumTracks.map((track) => track.artist).filter(Boolean)).size,
      };
    }

    if (selectedGenre) {
      return {
        tracks: tracks.filter((track) => (track.genres || []).includes(selectedGenre))
          .length,
      };
    }

    return {};
  }, [tracks, selectedArtist, selectedAlbum, selectedGenre]);

  const playlist = playlists.find((item) => item.id === selectedPlaylistId) || null;

  function getTitle() {
    if (activeView === "artists" || activeView === "albums" || activeView === "genres") {
      return "";
    }

    if (activeView === "playlist") return playlist?.name || "";
    if (activeView === "insights") return "Insights";
    if (activeView === "settings") return "Settings";

    return selectedArtist || selectedAlbum || selectedGenre || "Your Music";
  }

  function getSubtitle() {
    if (loading || error) return "";

    if (activeView === "artists" || activeView === "albums" || activeView === "genres") {
      return "";
    }

    if (activeView === "playlist") return `${playlistTracks.length} tracks`;
    if (activeView === "insights") return "Your listening behavior and trends";
    if (activeView === "settings") return "App preferences and playback options";

    if (selectedArtist) {
      return `${counts.tracks} tracks • ${counts.albums} albums`;
    }

    if (selectedAlbum) {
      return `${counts.tracks} tracks • ${counts.artists} artist${
        counts.artists === 1 ? "" : "s"
      }`;
    }

    if (selectedGenre) return `${counts.tracks} tracks`;

    return `${visibleTracks.length} tracks`;
  }

  const albumArtwork =
    activeView === "tracks" && selectedAlbum
      ? resolveAlbumArtwork(selectedAlbum, albumArtworkMap)
      : null;

  const showPlayButton =
    activeView === "tracks" && (selectedArtist || selectedAlbum || selectedGenre);

  return (
    <header className="main-content__header">
      {activeView === "tracks" && selectedArtist && artistArtworkPath && (
        <div className="artist-hero-banner">
          <img
            className="artist-hero-banner__image"
            src={artworkUrl(artistArtworkPath)}
            alt={`${selectedArtist} banner`}
          />
          <div className="artist-hero-banner__overlay" />
        </div>
      )}

      {albumArtwork?.type === "image" && (
        <div className="album-hero">
          <img
            className="album-hero__image"
            src={albumArtwork.src}
            alt={`${selectedAlbum} artwork`}
          />
        </div>
      )}

      <div className="main-content__header-row">
        <div>
          <h1>{getTitle()}</h1>

          {!loading && !error && (
            <div className="page-header__meta">
              <p className="main-content__subhead">{getSubtitle()}</p>

              {activeView === "tracks" && selectedArtist && artistGenres.length > 0 && (
                <div className="genre-badges">
                  {artistGenres.map((genre) => (
                    <span key={genre} className="genre-badge">
                      {genre}
                    </span>
                  ))}
                </div>
              )}

              {showPlayButton && (
                <button
                  className="page-header__play-button"
                  type="button"
                  onClick={() =>
                    playTracks(visibleTracks, {
                      source_type: selectedAlbum
                        ? "album"
                        : selectedArtist
                        ? "artist"
                        : "library",
                      source_id: null,
                    })
                  }
                  disabled={visibleTracks.length === 0}
                >
                  ▶ Play
                </button>
              )}
            </div>
          )}
        </div>

        {activeView === "tracks" && selectedArtist && (
          <div className="page-actions">
            <button
              className="page-actions__button"
              type="button"
              aria-label="Artist actions"
              aria-expanded={isActionsOpen}
              onClick={() => setIsActionsOpen((previous) => !previous)}
            >
              ⋯
            </button>

            {isActionsOpen && (
              <div className="page-actions__menu">
                <button
                  className="page-actions__menu-item"
                  type="button"
                  onClick={() => {
                    setIsActionsOpen(false);
                    setIsEditingArtist(true);
                  }}
                >
                  Edit Artist
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {isEditingArtist && selectedArtist && (
        <EditArtistModal
          artistName={selectedArtist}
          artworkPath={artistArtworkPath}
          onClose={() => setIsEditingArtist(false)}
        />
      )}
    </header>
  );
}
