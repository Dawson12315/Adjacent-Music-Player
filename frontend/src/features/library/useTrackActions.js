import { useCallback, useState } from "react";

import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { useDismissable } from "../../hooks/useDismissable";
import { resolveAlbumArtwork } from "../../utils/artwork";
import * as playlistsService from "../../services/playlistsService";

/**
 * Row-menu behaviour shared by the track lists: which menu is open, which way it opens,
 * and the actions it offers.
 *
 * Artwork no longer needs fetching here — the whole album artwork table arrives in one
 * request at startup, replacing one request per visible album.
 */
export function useTrackActions() {
  const { playlists, albumArtworkMap, openTrackEditor } = useLibrary();
  const { addToQueue } = usePlayer();
  const { notify } = useNotifications();

  const [openMenuTrackId, setOpenMenuTrackId] = useState(null);
  const [menuDirection, setMenuDirection] = useState("down");

  const closeMenu = useCallback(() => setOpenMenuTrackId(null), []);

  useDismissable(openMenuTrackId !== null, closeMenu);

  const toggleMenu = useCallback((trackId, direction) => {
    setMenuDirection(direction);
    setOpenMenuTrackId((previous) => (previous === trackId ? null : trackId));
  }, []);

  const handleAddToQueue = useCallback(
    (track) => {
      addToQueue(track);
      notify(`Added "${track.title}" to the queue.`);
      closeMenu();
    },
    [addToQueue, notify, closeMenu],
  );

  const handleAddToPlaylist = useCallback(
    async (trackId, playlistId) => {
      const playlist = playlists.find((item) => item.id === playlistId);

      try {
        await playlistsService.addTrackToPlaylist(playlistId, trackId);
        notify(`Added to ${playlist?.name || "playlist"}.`);
      } catch (error) {
        notify(error.message || "Could not add the track to that playlist.");
      } finally {
        closeMenu();
      }
    },
    [playlists, notify, closeMenu],
  );

  const handleEdit = useCallback(
    (track) => {
      openTrackEditor(track);
      closeMenu();
    },
    [openTrackEditor, closeMenu],
  );

  const artworkFor = useCallback(
    (track) => resolveAlbumArtwork(track.album, albumArtworkMap),
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
