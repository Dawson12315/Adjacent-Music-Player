import { useCallback, useEffect, useState } from "react";

import { StateMessage } from "../../components/StateMessage";
import { TrackRow } from "../library/TrackRow";
import { useTrackActions } from "../library/useTrackActions";
import { SimilarTracksSection } from "../recommendations/SimilarTracksSection";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { useNavigation } from "../../hooks/useNavigation";
import * as playlistsService from "../../services/playlistsService";
import { isLikedSongsPlaylist } from "../../utils/playlists";

export function PlaylistView() {
  const {
    playlists,
    playlistTracks,
    setPlaylistTracks,
    loadPlaylistTracks,
  } = useLibrary();
  const { currentTrack, playTrack, isLiked } = usePlayer();
  const { selectedPlaylistId } = useNavigation();
  const { notify } = useNotifications();

  const [isLoading, setIsLoading] = useState(true);

  const playlist = playlists.find((item) => item.id === selectedPlaylistId) || null;
  const isLikedPlaylist = isLikedSongsPlaylist(playlist);

  const actions = useTrackActions(playlistTracks);

  // Liking or unliking from the player bar changes what belongs in Ducking Good, so that
  // playlist reloads when the liked state flips while it is open. Other playlists ignore it.
  const likedRevision = isLikedPlaylist ? isLiked : null;

  useEffect(() => {
    if (!selectedPlaylistId) {
      return undefined;
    }

    const controller = new AbortController();

    async function run() {
      setIsLoading(true);

      try {
        await loadPlaylistTracks(selectedPlaylistId, { signal: controller.signal });
      } catch (error) {
        if (error.name !== "AbortError") {
          notify(error.message || "Could not load this playlist.");
          setPlaylistTracks([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    run();

    return () => controller.abort();
  }, [selectedPlaylistId, loadPlaylistTracks, setPlaylistTracks, notify, likedRevision]);

  const handlePlay = useCallback(
    (track) => {
      actions.closeMenu();
      playTrack(track, playlistTracks, {
        source_type: "playlist",
        source_id: selectedPlaylistId,
      });
    },
    [actions, playTrack, playlistTracks, selectedPlaylistId],
  );

  const handleRemoveFromPlaylist = useCallback(
    async (trackId) => {
      try {
        await playlistsService.removeTrackFromPlaylist(selectedPlaylistId, trackId);
        setPlaylistTracks((previous) => previous.filter((track) => track.id !== trackId));
      } catch (error) {
        notify(error.message || "Could not remove the track from this playlist.");
      } finally {
        actions.closeMenu();
      }
    },
    [selectedPlaylistId, notify, actions, setPlaylistTracks],
  );

  const handleAddRecommendation = useCallback(
    async (track) => {
      try {
        await playlistsService.addTrackToPlaylist(selectedPlaylistId, track.id);
        setPlaylistTracks((previous) => [...previous, track]);
      } catch (error) {
        notify(error.message || "Could not add that track to the playlist.");
      }
    },
    [selectedPlaylistId, notify, setPlaylistTracks],
  );

  if (isLoading) {
    return <StateMessage>Loading playlist...</StateMessage>;
  }

  if (playlistTracks.length === 0) {
    return <StateMessage>This Playlist is empty.</StateMessage>;
  }

  return (
    <>
      <div className="track-list">
        {playlistTracks.map((track, index) => (
          <TrackRow
            key={track.id}
            track={track}
            index={index}
            isActive={currentTrack?.id === track.id}
            artwork={actions.artworkFor(track)}
            playlists={actions.playlists}
            isMenuOpen={actions.openMenuTrackId === track.id}
            menuDirection={actions.menuDirection}
            onPlay={handlePlay}
            onToggleMenu={actions.toggleMenu}
            onEdit={actions.handleEdit}
            onAddToQueue={actions.handleAddToQueue}
            onAddToPlaylist={actions.handleAddToPlaylist}
            onRemoveFromPlaylist={handleRemoveFromPlaylist}
          />
        ))}
      </div>

      <SimilarTracksSection
        playlistId={selectedPlaylistId}
        onPlay={handlePlay}
        onAdd={handleAddRecommendation}
      />
    </>
  );
}
