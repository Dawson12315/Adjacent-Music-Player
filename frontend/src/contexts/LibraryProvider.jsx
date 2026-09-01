import { useCallback, useEffect, useMemo, useState } from "react";

import { LibraryContext } from "./LibraryContext";
import { useAuth } from "./AuthContext";
import * as albumsService from "../services/albumsService";
import * as artistsService from "../services/artistsService";
import * as genresService from "../services/genresService";
import * as playlistsService from "../services/playlistsService";
import * as tracksService from "../services/tracksService";
import { sortPlaylistsWithSystemFirst, upsertPlaylist } from "../utils/playlists";

/**
 * Owns the catalogue metadata that is small enough to hold in memory, and nothing else.
 *
 * The tracks themselves are NOT loaded here any more. Fetching all 36,534 of them meant
 * 21 MB of uncompressed JSON on every startup, parsed into 36,534 objects and filtered in
 * JavaScript on every keystroke. Tracks are now paged from the server by whichever view
 * needs them (see useTrackFeed).
 *
 * What stays: the artist, album and genre name lists — roughly 125 KB combined, and used
 * for browsing and for the metadata editor's pickers — plus playlists and the two artwork
 * lookup tables, each of which is now a single request instead of one per entity.
 */
export function LibraryProvider({ children }) {
  const { currentUser } = useAuth();

  const [artists, setArtists] = useState([]);
  const [albums, setAlbums] = useState([]);
  const [genres, setGenres] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [trackCount, setTrackCount] = useState(0);
  const [albumArtworkMap, setAlbumArtworkMap] = useState({});
  const [artistArtworkMap, setArtistArtworkMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  /** Which track the metadata editor is open for. */
  const [editingTrack, setEditingTrack] = useState(null);

  /** Tracks of the playlist currently open — the header shows the count. */
  const [playlistTracks, setPlaylistTracks] = useState([]);

  const loadLibrary = useCallback(async (signal) => {
    const [
      artistsData,
      albumsData,
      genresData,
      playlistsData,
      countData,
      albumArtwork,
      artistArtwork,
    ] = await Promise.all([
      artistsService.listArtists({ signal }),
      albumsService.listAlbums({ signal }),
      genresService.listGenres({ signal }),
      playlistsService.listPlaylists({ signal }),
      tracksService.getTrackCount({ signal }),
      albumsService.getAllAlbumArtwork({ signal }),
      artistsService.getAllArtistArtwork({ signal }),
    ]);

    setArtists(artistsData);
    setAlbums(albumsData);
    setGenres(genresData);
    setPlaylists(sortPlaylistsWithSystemFirst(playlistsData));
    setTrackCount(countData.count ?? 0);
    setAlbumArtworkMap(albumArtwork);
    setArtistArtworkMap(artistArtwork);
  }, []);

  useEffect(() => {
    if (!currentUser) {
      return undefined;
    }

    const controller = new AbortController();

    async function run() {
      try {
        await loadLibrary(controller.signal);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message || "Could not load your library.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    run();

    return () => controller.abort();
  }, [currentUser, loadLibrary]);

  /** Re-read after a scan, cleanup or artist rename changes the catalogue wholesale. */
  const refreshLibrary = useCallback(async () => {
    await loadLibrary();
  }, [loadLibrary]);

  const clearTracks = useCallback(() => {
    setArtists([]);
    setAlbums([]);
    setGenres([]);
    setTrackCount(0);
    setPlaylistTracks([]);
  }, []);

  /**
   * Open the metadata editor.
   *
   * Tracks reaching this from a playlist or the similar list come from endpoints that
   * return raw ORM rows with an empty `genres` array. The authoritative copy is fetched
   * first, which is what stops the editor seeding an empty genre list and then wiping the
   * track's genres on save — `PATCH /api/tracks/{id}` replaces rather than merges.
   */
  const openTrackEditor = useCallback(async (track) => {
    setEditingTrack(track);

    if (track.metadataComplete) {
      return;
    }

    try {
      const full = await tracksService.getTrack(track.id);
      setEditingTrack((current) => (current?.id === full.id ? full : current));
    } catch (err) {
      // Leave the partial track in place; the editor will not submit genres for it.
      console.error("Could not load full track metadata", err);
    }
  }, []);

  const closeTrackEditor = useCallback(() => setEditingTrack(null), []);

  const loadPlaylistTracks = useCallback(async (playlistId, options) => {
    const data = await playlistsService.getPlaylistTracks(playlistId, options);
    setPlaylistTracks(data);
    return data;
  }, []);

  /* ---------- artwork ---------- */

  const setAlbumArtwork = useCallback((key, path) => {
    setAlbumArtworkMap((previous) => ({
      ...previous,
      [key]: path ? `${path}?v=${Date.now()}` : "",
    }));
  }, []);

  const setArtistArtwork = useCallback((key, path) => {
    setArtistArtworkMap((previous) => ({
      ...previous,
      [key]: path ? `${path}?v=${Date.now()}` : "",
    }));
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
      artists,
      albums,
      genres,
      playlists,
      trackCount,
      loading,
      error,
      albumArtworkMap,
      artistArtworkMap,
      setAlbumArtwork,
      setArtistArtwork,
      refreshLibrary,
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
      artists,
      albums,
      genres,
      playlists,
      trackCount,
      loading,
      error,
      albumArtworkMap,
      artistArtworkMap,
      setAlbumArtwork,
      setArtistArtwork,
      refreshLibrary,
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
