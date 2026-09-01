import { useEffect, useState } from "react";

import { Artwork } from "./Artwork";
import { Icon } from "./Icon";
import { EditArtistModal } from "../features/metadata/EditArtistModal";
import { useLibrary } from "../contexts/LibraryContext";
import { usePageMeta } from "../contexts/PageMetaContext";
import { usePlayer } from "../contexts/PlayerContext";
import { useDismissable } from "../hooks/useDismissable";
import { useNavigation } from "../hooks/useNavigation";
import { getArtistGenres } from "../services/artistsService";
import { artworkUrl } from "../config";
import { resolveAlbumArtwork } from "../utils/artwork";

/**
 * One page header for every view.
 *
 * Replaces two competing systems: a shared h1 that rendered *empty* on the artists,
 * albums and genres views, plus a per-view hero block whose CSS was written out four
 * times identically and then drifted — three collapsing to a column at 700px and the
 * fourth at 1100px.
 */
export function PageHeader() {
  const { artists, albums, genres, playlists, playlistTracks, trackCount, albumArtworkMap, artistArtworkMap } =
    useLibrary();
  const { meta } = usePageMeta();
  const { playTracks } = usePlayer();
  const {
    activeView,
    selectedArtist,
    selectedAlbum,
    selectedGenre,
    selectedPlaylistId,
  } = useNavigation();

  const [artistData, setArtistData] = useState({ artist: null, genres: [] });
  const [isActionsOpen, setIsActionsOpen] = useState(false);
  const [isEditingArtist, setIsEditingArtist] = useState(false);

  useDismissable(isActionsOpen, () => setIsActionsOpen(false));

  // Held with the artist it describes, so switching artists clears the previous one by
  // derivation rather than by resetting state from an effect.
  const artistGenres =
    selectedArtist && artistData.artist === selectedArtist ? artistData.genres : [];

  useEffect(() => {
    if (!selectedArtist) {
      return undefined;
    }

    const controller = new AbortController();

    getArtistGenres(selectedArtist, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setArtistData({ artist: selectedArtist, genres: data || [] });
        }
      })
      .catch((error) => {
        if (error.name !== "AbortError") {
          setArtistData({ artist: selectedArtist, genres: [] });
        }
      });

    return () => controller.abort();
  }, [selectedArtist]);

  // Home owns its own greeting.
  if (activeView === "home") {
    return null;
  }

  const playlist = playlists.find((item) => item.id === selectedPlaylistId) || null;
  const artistArtworkPath = selectedArtist ? artistArtworkMap[selectedArtist] : null;
  const albumArtwork = selectedAlbum
    ? resolveAlbumArtwork(selectedAlbum, albumArtworkMap)
    : null;

  const isEntityView = Boolean(selectedArtist || selectedAlbum || selectedGenre);
  const feedTracks = meta.tracks || [];

  const config = {
    tracks: {
      eyebrow: "Library",
      title: "Your Music",
      stat: { value: trackCount, label: "tracks" },
    },
    artists: {
      eyebrow: "Library",
      title: "Artists",
      lede: "Browse your collection by artist.",
      stat: { value: artists.length, label: "artists" },
    },
    albums: {
      eyebrow: "Library",
      title: "Albums",
      lede: "Browse your albums by artwork or as a list.",
      stat: { value: albums.length, label: "albums" },
    },
    genres: {
      eyebrow: "Library map",
      title: "Genres",
      lede: "Explore your library by sound, mood and style.",
      stat: { value: genres.length, label: "genres" },
    },
    playlist: {
      eyebrow: "Playlist",
      title: playlist?.name || "Playlist",
      stat: { value: playlistTracks.length, label: "tracks" },
    },
    insights: {
      eyebrow: "Listening analytics",
      title: "Insights",
      lede: "What you play most, skip most, and keep coming back to.",
    },
    settings: {
      eyebrow: "Configuration",
      title: "Settings",
      lede: "App preferences, library maintenance and integrations.",
    },
  }[activeView] || {};

  // An artist, album or genre replaces the generic library header.
  const title = isEntityView
    ? selectedArtist || selectedAlbum || selectedGenre
    : config.title;

  const eyebrow = isEntityView
    ? selectedArtist
      ? "Artist"
      : selectedAlbum
      ? "Album"
      : "Genre"
    : config.eyebrow;

  // Only entity views show an inline count; list views get the stat block on the right,
  // and showing both was the same number printed twice.
  const count = isEntityView ? meta.count : null;

  const hasHero = Boolean(selectedArtist && artistArtworkPath);

  return (
    <header className={`page-header ${hasHero ? "page-header--hero" : ""}`}>
      {hasHero && (
        <div className="page-header__backdrop">
          <img src={artworkUrl(artistArtworkPath)} alt="" loading="eager" decoding="async" />
        </div>
      )}

      <div className="page-header__row">
        <div>
          {eyebrow && <p className="eyebrow page-header__eyebrow">{eyebrow}</p>}

          <h1 className="page-header__title">{title}</h1>

          {config.lede && <p className="page-header__lede">{config.lede}</p>}

          <div className="page-header__meta">
            {selectedAlbum && albumArtwork?.type === "image" && (
              <Artwork
                artwork={albumArtwork}
                className="page-header__album-art"
                size={72}
                eager
              />
            )}

            {typeof count === "number" && (
              <span className="page-header__count">
                {count.toLocaleString()} tracks
              </span>
            )}

            {isEntityView && feedTracks.length > 0 && (
              <button
                className="btn btn--accent btn--sm"
                type="button"
                onClick={() =>
                  playTracks(feedTracks, {
                    source_type: selectedAlbum
                      ? "album"
                      : selectedArtist
                      ? "artist"
                      : "library",
                    source_id: null,
                  })
                }
              >
                <Icon name="play" size={14} />
                Play
              </button>
            )}

            {artistGenres.length > 0 && (
              <span className="page-header__badges">
                {artistGenres.slice(0, 5).map((genre) => (
                  <span key={genre} className="pill">
                    {genre}
                  </span>
                ))}
              </span>
            )}
          </div>
        </div>

        {!isEntityView && config.stat && (
          <div className="page-header__stat">
            <span className="page-header__stat-value">
              {config.stat.value.toLocaleString()}
            </span>
            <span className="page-header__stat-label">{config.stat.label}</span>
          </div>
        )}

        {selectedArtist && (
          <div className="page-actions" data-dismissable-root={isActionsOpen ? "" : undefined}>
            <button
              className="btn btn--icon btn--ghost"
              type="button"
              aria-label="Artist actions"
              aria-expanded={isActionsOpen}
              onClick={() => setIsActionsOpen((open) => !open)}
            >
              <Icon name="more" size={18} />
            </button>

            {isActionsOpen && (
              <div className="menu menu--right menu--down">
                <button
                  className="menu__item"
                  type="button"
                  onClick={() => {
                    setIsActionsOpen(false);
                    setIsEditingArtist(true);
                  }}
                >
                  Edit artist
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
