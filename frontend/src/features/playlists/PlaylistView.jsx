import { useCallback, useEffect, useState } from "react";

import { Icon } from "../../components/Icon";
import { TrackListSkeleton } from "../library/TrackListSkeleton";
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
  const { playlists, playlistTracks, setPlaylistTracks, loadPlaylistTracks } = useLibrary();
  const { currentTrack, isPlaying, playTrack, isLiked } = usePlayer();
  const { selectedPlaylistId } = useNavigation();
  const { notify } = useNotifications();

  const [isLoading, setIsLoading] = useState(true);

  const playlist = playlists.find((item) => item.id === selectedPlaylistId) || null;
  const isLikedPlaylist = isLikedSongsPlaylist(playlist);
  const actions = useTrackActions();

  // Liking from the player bar changes what belongs in Ducking Good, so that playlist
  // reloads when the liked state flips while it is open. Others ignore it.
  const likedRevision = isLikedPlaylist ? isLiked : null;

  useEffect(() => {
    if (!selectedPlaylistId) return undefined;

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
        if (!controller.signal.aborted) setIsLoading(false);
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

  const handleRemove = useCallback(
    async (trackId) => {
      try {
        await playlistsService.removeTrackFromPlaylist(selectedPlaylistId, trackId);
        setPlaylistTracks((previous) => previous.filter((t) => t.id !== trackId));
      } catch (error) {
        notify(error.message || "Could not remove the track.");
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
        notify(`Added "${track.title}".`);
      } catch (error) {
        notify(error.message || "Could not add that track.");
      }
    },
    [selectedPlaylistId, notify, setPlaylistTracks],
  );

  if (isLoading) {
    return <TrackListSkeleton />;
  }

  if (playlistTracks.length === 0) {
    return (
      <>
        <div className="state">
          <div className="state__icon">
            <Icon name="music" size={20} />
          </div>
          <p className="state__title">This playlist is empty</p>
          <p className="state__text">
            {isLikedPlaylist
              ? "Tap the heart on any track and it will show up here."
              : "Use the ⋯ menu on any track to add it to this playlist."}
          </p>
        </div>

        <SimilarTracksSection
          playlistId={selectedPlaylistId}
          onPlay={handlePlay}
          onAdd={handleAddRecommendation}
        />
      </>
    );
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
            isPlaying={isPlaying}
            artwork={actions.artworkFor(track)}
            playlists={actions.playlists}
            isMenuOpen={actions.openMenuTrackId === track.id}
            menuDirection={actions.menuDirection}
            onPlay={handlePlay}
            onToggleMenu={actions.toggleMenu}
            onEdit={actions.handleEdit}
            onAddToQueue={actions.handleAddToQueue}
            onAddToPlaylist={actions.handleAddToPlaylist}
            onRemoveFromPlaylist={handleRemove}
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
