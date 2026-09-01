import { useCallback, useMemo } from "react";

import { Pagination } from "../../components/Pagination";
import { StateMessage } from "../../components/StateMessage";
import { TrackRow } from "./TrackRow";
import { SimilarTracksSection } from "../recommendations/SimilarTracksSection";
import { useLibrary } from "../../contexts/LibraryContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { useNavigation } from "../../hooks/useNavigation";
import { useLibraryFilters, usePagination } from "./useLibraryFilters";
import { useTrackActions } from "./useTrackActions";

const TRACKS_PAGE_SIZE = 50;

export function TracksView() {
  const { loading, error } = useLibrary();
  const { currentTrack, playTrack } = usePlayer();
  const {
    selectedArtist,
    selectedAlbum,
    selectedGenre,
    page,
    setPage,
    clearFilters,
  } = useNavigation();

  const { visibleTracks } = useLibraryFilters();
  const { pageItems, totalPages, page: safePage } = usePagination(
    visibleTracks,
    page,
    TRACKS_PAGE_SIZE,
  );

  const actions = useTrackActions(pageItems);

  const listeningSource = useMemo(
    () => ({
      source_type: selectedAlbum ? "album" : selectedArtist ? "artist" : "library",
      source_id: null,
    }),
    [selectedAlbum, selectedArtist],
  );

  const handlePlay = useCallback(
    (track) => {
      actions.closeMenu();
      playTrack(track, visibleTracks, listeningSource);
    },
    [actions, playTrack, visibleTracks, listeningSource],
  );

  if (loading) {
    return <StateMessage>Loading tracks...</StateMessage>;
  }

  if (error) {
    return <StateMessage>{error}</StateMessage>;
  }

  if (visibleTracks.length === 0) {
    return <StateMessage>No matching tracks found.</StateMessage>;
  }

  // Recommendations follow the playing track when it is part of this list, otherwise the
  // first row, and only appear when browsing a specific artist or album.
  const showSimilar = Boolean(selectedArtist || selectedAlbum) && !selectedGenre;
  const similarSource =
    currentTrack && visibleTracks.some((track) => track.id === currentTrack.id)
      ? currentTrack
      : visibleTracks[0] || null;

  return (
    <div className="track-list">
      {selectedArtist && (
        <button className="filter-pill" onClick={clearFilters} type="button">
          Showing artist: {selectedArtist} ×
        </button>
      )}

      {selectedAlbum && (
        <button className="filter-pill" onClick={clearFilters} type="button">
          Showing album: {selectedAlbum} ×
        </button>
      )}

      {pageItems.map((track, index) => (
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
        />
      ))}

      <Pagination page={safePage} totalPages={totalPages} onChange={setPage} />

      {showSimilar && similarSource && (
        <SimilarTracksSection sourceTrack={similarSource} onPlay={handlePlay} />
      )}
    </div>
  );
}
