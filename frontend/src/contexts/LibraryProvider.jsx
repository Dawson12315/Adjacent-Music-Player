import { useCallback, useEffect, useMemo, useState } from "react";

import { LibraryContext } from "./LibraryContext";
import { useAuth } from "./AuthContext";
import { useArtworkCache } from "../hooks/useArtworkCache";
import * as albumsService from "../services/albumsService";
import * as artistsService from "../services/artistsService";
import * as genresService from "../services/genresService";
import * as playlistsService from "../services/playlistsService";
import * as tracksService from "../services/tracksService";
import { sortPlaylistsWithSystemFirst, upsertPlaylist } from "../utils/playlists";

/**
 * Owns the library catalogue and the artwork caches.
 *
 * The whole library is still loaded up front and filtered in the browser, matching the
 * previous behaviour — search here also matches genre and needs no further round trips,
 * and changing that would change what users see. The oversized initial payload is worth
 * revisiting on its own.
 *
 * Two calls the old startup sequence made are gone: the liked-songs playlist, fetched
 * into state nothing ever read yet still gating the entire load, and the admin-only
 * settings and readiness reads, which now load with the settings screen that uses them.
 */
export function LibraryProvider({ children }) {
  const { currentUser } = useAuth();

  const [tracks, setTracks] = useState([]);
  const [artists, setArtists] = useState([]);
  const [albums, setAlbums] = useState([]);
  const [genres, setGenres] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Which track the metadata editor is open for. Lives here because the editor is opened
  // from two different views and commits through this context's update path.
  const [editingTrack, setEditingTrack] = useState(null);

  // Tracks of the playlist currently open. Shared because the page header shows the
  // count while the view below it renders the rows.
  const [playlistTracks, setPlaylistTracks] = useState([]);

  const albumArtwork = useArtworkCache(albumsService.getAlbumArtwork);
  const artistArtwork = useArtworkCache(artistsService.getArtistArtwork);

  const loadLibrary = useCallback(async () => {
    const [tracksData, artistsData, albumsData, genresData, playlistsData] =
      await Promise.all([
        tracksService.listTracks(),
        artistsService.listArtists(),
        albumsService.listAlbums(),
        genresService.listGenres(),
        playlistsService.listPlaylists(),
      ]);

    setTracks(tracksData);
    setArtists(artistsData);
    setAlbums(albumsData);
    setGenres(genresData);
    setPlaylists(sortPlaylistsWithSystemFirst(playlistsData));
  }, []);

  useEffect(() => {
    if (!currentUser) {
      return undefined;
    }

    let cancelled = false;

    async function run() {
      try {
        await loadLibrary();
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load tracks.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, [currentUser, loadLibrary]);

  /**
   * Re-read the catalogue after an operation that can change it wholesale — a scan,
   * a cleanup, or an artist rename. This block was previously pasted into three handlers.
   */
  const refreshLibrary = useCallback(async () => {
    await loadLibrary();
  }, [loadLibrary]);

  /** Apply a track edit everywhere it appears, without a full reload. */
  const applyTrackUpdate = useCallback((updatedTrack) => {
    setTracks((previous) => {
      const next = previous.map((track) =>
        track.id === updatedTrack.id ? updatedTrack : track,
      );

      // Derived from the updated list, not the pre-edit one.
      setArtists(
        Array.from(new Set(next.map((track) => track.artist).filter(Boolean))).sort(
          (a, b) => a.localeCompare(b),
        ),
      );

      setAlbums(
        Array.from(new Set(next.map((track) => track.album).filter(Boolean))).sort(
          (a, b) => a.localeCompare(b),
        ),
      );

      return next;
    });
  }, []);

  const clearTracks = useCallback(() => {
    setTracks([]);
    setArtists([]);
    setAlbums([]);
    setGenres([]);
    setPlaylistTracks([]);
  }, []);

  /**
   * Open the metadata editor.
   *
   * Tracks reaching this from a playlist or the similar-tracks list come from endpoints
   * that return raw ORM rows with an empty `genres` array. Resolving against the library
   * copy first is what stops the editor from seeding an empty genre list and then wiping
   * the track's genres on save, since `PATCH /api/tracks/{id}` replaces rather than merges.
   */
  const openTrackEditor = useCallback(
    (track) => {
      const authoritative = tracks.find((item) => item.id === track.id);
      setEditingTrack(authoritative || track);
    },
    [tracks],
  );

  const closeTrackEditor = useCallback(() => setEditingTrack(null), []);

  const loadPlaylistTracks = useCallback(async (playlistId, options) => {
    const data = await playlistsService.getPlaylistTracks(playlistId, options);
    setPlaylistTracks(data);
    return data;
  }, []);

  /* ---------- playlist mutations ---------- */

  const createPlaylist = useCallback(async (name) => {
    const created = await playlistsService.createPlaylist(name);
    setPlaylists((previous) => upsertPlaylist(previous, created));
    return created;
  }, []);

  const renamePlaylist = useCallback(async (playlistId, name) => {
    const updated = await playlistsService.renamePlaylist(playlistId, name);
    setPlaylists((previous) => upsertPlaylist(previous, updated));
    return updated;
  }, []);

  const deletePlaylist = useCallback(async (playlistId) => {
    await playlistsService.deletePlaylist(playlistId);
    setPlaylists((previous) => previous.filter((item) => item.id !== playlistId));
  }, []);

  const updatePlaylistArtwork = useCallback(async (playlistId, file) => {
    const updated = await playlistsService.uploadPlaylistArtwork(playlistId, file);
    setPlaylists((previous) => upsertPlaylist(previous, updated));
    return updated;
  }, []);

  const value = useMemo(
    () => ({
      tracks,
      artists,
      albums,
      genres,
      playlists,
      loading,
      error,
      albumArtworkMap: albumArtwork.map,
      ensureAlbumArtwork: albumArtwork.ensure,
      setAlbumArtwork: albumArtwork.set,
      artistArtworkMap: artistArtwork.map,
      ensureArtistArtwork: artistArtwork.ensure,
      setArtistArtwork: artistArtwork.set,
      refreshLibrary,
      applyTrackUpdate,
      clearTracks,
      editingTrack,
      openTrackEditor,
      closeTrackEditor,
      playlistTracks,
      setPlaylistTracks,
      loadPlaylistTracks,
      createPlaylist,
      renamePlaylist,
      deletePlaylist,
      updatePlaylistArtwork,
    }),
    [
      tracks,
      artists,
      albums,
      genres,
      playlists,
      loading,
      error,
      albumArtwork.map,
      albumArtwork.ensure,
      albumArtwork.set,
      artistArtwork.map,
      artistArtwork.ensure,
      artistArtwork.set,
      refreshLibrary,
      applyTrackUpdate,
      clearTracks,
      editingTrack,
      openTrackEditor,
      closeTrackEditor,
      playlistTracks,
      loadPlaylistTracks,
      createPlaylist,
      renamePlaylist,
      deletePlaylist,
      updatePlaylistArtwork,
    ],
  );

  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>;
}
