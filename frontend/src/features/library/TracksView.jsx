import { useCallback, useEffect, useMemo } from "react";

import { Icon } from "../../components/Icon";
import { TrackListSkeleton } from "./TrackListSkeleton";
import { TrackRow } from "./TrackRow";
import { SimilarTracksSection } from "../recommendations/SimilarTracksSection";
import { usePageMeta } from "../../contexts/PageMetaContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { useInfiniteScroll } from "../../hooks/useInfiniteScroll";
import { useNavigation } from "../../hooks/useNavigation";
import { useTrackFeed } from "./useTrackFeed";
import { useTrackActions } from "./useTrackActions";

export function TracksView() {
  const { currentTrack, isPlaying, playTrack } = usePlayer();
  const { selectedArtist, selectedAlbum, selectedGenre, searchQuery } = useNavigation();

  const feed = useTrackFeed();
  const actions = useTrackActions();
  const { setPageMeta } = usePageMeta();

  // The header sits above this view and needs both to render its count and Play button.
  useEffect(() => {
    setPageMeta({ count: feed.total, tracks: feed.tracks });
  }, [feed.total, feed.tracks, setPageMeta]);

  const { setSentinel } = useInfiniteScroll({
    onLoadMore: feed.loadMore,
    enabled: feed.hasMore && !feed.isLoading,
  });

  const listeningSource = useMemo(
    () => ({
      source_type: selectedAlbum
        ? "album"
        : selectedArtist
        ? "artist"
        : selectedGenre
        ? "library"
        : "library",
      source_id: null,
    }),
    [selectedAlbum, selectedArtist, selectedGenre],
  );

  /*
   * The queue is built from what has actually been loaded. For an artist or album that is
   * the complete list; for the paged library feed it is everything scrolled so far, which
   * then grows as more arrives.
   */
  const handlePlay = useCallback(
    (track) => {
      actions.closeMenu();
      playTrack(track, feed.tracks, listeningSource);
    },
    [actions, playTrack, feed.tracks, listeningSource],
  );

  if (feed.isLoading) {
    return <TrackListSkeleton />;
  }

  if (feed.error) {
    return (
      <div className="state state--error">
        <div className="state__icon">
          <Icon name="close" size={20} />
        </div>
        <p className="state__title">Could not load tracks</p>
        <p className="state__text">{feed.error}</p>
      </div>
    );
  }

  if (feed.tracks.length === 0) {
    return (
      <div className="state">
        <div className="state__icon">
          <Icon name="search" size={20} />
        </div>
        <p className="state__title">
          {searchQuery ? "No matches" : "Nothing here yet"}
        </p>
        <p className="state__text">
          {searchQuery
            ? `Nothing in your library matches "${searchQuery}".`
            : "Scan your music library from Settings to get started."}
        </p>
      </div>
    );
  }

  const showSimilar = Boolean(selectedArtist || selectedAlbum) && !selectedGenre;
  const similarSource =
    currentTrack && feed.tracks.some((track) => track.id === currentTrack.id)
      ? currentTrack
      : feed.tracks[0] || null;

  return (
    <>
      <div className="track-list">
        {feed.tracks.map((track, index) => (
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
          />
        ))}
      </div>

      {feed.hasMore && (
        <div className="load-more" ref={setSentinel}>
          {feed.isLoadingMore ? (
            <span className="load-more__status">Loading more…</span>
          ) : (
            <button className="btn btn--sm" type="button" onClick={feed.loadMore}>
              Load more
            </button>
          )}
          <span className="load-more__status">
            {feed.tracks.length.toLocaleString()} of {feed.total.toLocaleString()}
          </span>
        </div>
      )}

      {showSimilar && similarSource && (
        <SimilarTracksSection sourceTrack={similarSource} onPlay={handlePlay} />
      )}
    </>
  );
}
