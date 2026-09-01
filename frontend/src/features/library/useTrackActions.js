import { useCallback, useEffect, useState } from "react";

import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { getAlbumKey, resolveAlbumArtwork } from "../../utils/artwork";
import * as playlistsService from "../../services/playlistsService";

/**
 * The row-menu behaviour shared by the tracks and playlist views: which menu is open,
 * which way it opens, and the actions the menu offers.
 *
 * Album artwork for the visible rows is requested here too, keyed off a stable signature
 * so the effect fires when the visible set actually changes rather than on every render.
 */
export function useTrackActions(visibleTracks) {
  const { playlists, albumArtworkMap, ensureAlbumArtwork, openTrackEditor } = useLibrary();
  const { addToQueue } = usePlayer();
  const { notify } = useNotifications();

  const [openMenuTrackId, setOpenMenuTrackId] = useState(null);
  const [menuDirection, setMenuDirection] = useState("down");

  const albumKeys = visibleTracks
    .map((track) => getAlbumKey(track.album))
    .filter(Boolean);

  const albumSignature = albumKeys.join("|");

  useEffect(() => {
    if (albumKeys.length > 0) {
      ensureAlbumArtwork(albumKeys);
    }
  }, [albumSignature, ensureAlbumArtwork]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleMenu = useCallback((trackId, direction) => {
    setMenuDirection(direction);
    setOpenMenuTrackId((previous) => (previous === trackId ? null : trackId));
  }, []);

  const closeMenu = useCallback(() => setOpenMenuTrackId(null), []);

  const handleAddToQueue = useCallback(
    (track) => {
      addToQueue(track);
      closeMenu();
    },
    [addToQueue, closeMenu],
  );

  const handleAddToPlaylist = useCallback(
    async (trackId, playlistId) => {
      try {
        await playlistsService.addTrackToPlaylist(playlistId, trackId);
        notify("Added to playlist.");
      } catch (error) {
        notify(error.message || "Could not add the track to that playlist.");
      } finally {
        closeMenu();
      }
    },
    [notify, closeMenu],
  );

  const handleEdit = useCallback(
    (track) => {
      openTrackEditor(track);
      closeMenu();
    },
    [openTrackEditor, closeMenu],
  );

  const artworkFor = useCallback(
    (track) => (track.album ? resolveAlbumArtwork(track.album, albumArtworkMap) : null),
    [albumArtworkMap],
  );

  return {
    playlists,
    openMenuTrackId,
    menuDirection,
    toggleMenu,
    closeMenu,
    handleAddToQueue,
    handleAddToPlaylist,
    handleEdit,
    artworkFor,
  };
}
