import { useCallback, useEffect, useRef, useState } from "react";

import { useNavigation } from "../../hooks/useNavigation";
import * as tracksService from "../../services/tracksService";

const PAGE_SIZE = 60;
const SEARCH_DEBOUNCE_MS = 250;

/** Fired on window by the edit modal when a track's metadata is saved. */
export const TRACK_UPDATED_EVENT = "adjacent:track-updated";

/**
 * Supplies the tracks for whatever the current route is asking for.
 *
 * The library feed is paged from the server and grows by infinite scroll. Artist and
 * album views fetch their entity's tracks in one request — a few hundred rows at most —
 * so the queue built from them is always complete. Genre views page like the library.
 *
 * This replaces holding all 36,534 tracks in memory and filtering them on every keystroke.
 */
export function useTrackFeed() {
  const { selectedArtist, selectedAlbum, selectedGenre, searchQuery } = useNavigation();

  const [tracks, setTracks] = useState([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState(searchQuery);

  const offsetRef = useRef(0);
  const loadingRef = useRef(false);

  // Typing should not fire a request per keystroke.
  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedSearch(searchQuery), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [searchQuery]);

  /** What the current route is asking for, as a stable key. */
  const source = selectedArtist
    ? `artist:${selectedArtist}`
    : selectedAlbum
    ? `album:${selectedAlbum}`
    : selectedGenre
    ? `genre:${selectedGenre}`
    : `library:${debouncedSearch}`;

  const fetchPage = useCallback(
    async (offset, signal) => {
      if (selectedArtist) {
        const items = await tracksService.getArtistTracks(selectedArtist, { signal });
        return { items, total: items.length, hasMore: false };
      }

      if (selectedAlbum) {
        const items = await tracksService.getAlbumTracks(selectedAlbum, { signal });
        return { items, total: items.length, hasMore: false };
      }

      if (selectedGenre) {
        return tracksService.getGenreTracks(selectedGenre, {
          limit: PAGE_SIZE,
          offset,
          signal,
        });
      }

      return tracksService.listTracksPage({
        limit: PAGE_SIZE,
        offset,
        search: debouncedSearch,
        signal,
      });
    },
    [selectedArtist, selectedAlbum, selectedGenre, debouncedSearch],
  );

  // First page, and a full reset whenever the source changes.
  useEffect(() => {
    const controller = new AbortController();

    offsetRef.current = 0;
    setIsLoading(true);
    setError("");

    async function run() {
      try {
        const page = await fetchPage(0, controller.signal);

        if (controller.signal.aborted) return;

        setTracks(page.items);
        setTotal(page.total);
        setHasMore(page.hasMore);
        offsetRef.current = page.items.length;
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message || "Could not load tracks.");
          setTracks([]);
          setTotal(0);
          setHasMore(false);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    run();

    return () => controller.abort();
    // `source` captures every input to fetchPage; depending on it keeps the reset to one
    // run per actual change of what is being asked for.
  }, [source]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadMore = useCallback(async () => {
    if (loadingRef.current || !hasMore) {
      return;
    }

    loadingRef.current = true;
    setIsLoadingMore(true);

    try {
      const page = await fetchPage(offsetRef.current);

      setTracks((previous) => {
        // Guard against a duplicate page if two loads race.
        const seen = new Set(previous.map((track) => track.id));
        const fresh = page.items.filter((track) => !seen.has(track.id));
        return [...previous, ...fresh];
      });

      setHasMore(page.hasMore);
      offsetRef.current += page.items.length;
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err.message || "Could not load more tracks.");
        setHasMore(false);
      }
    } finally {
      loadingRef.current = false;
      setIsLoadingMore(false);
    }
  }, [fetchPage, hasMore]);

  /** Reflect a metadata edit without refetching the page. */
  const replaceTrack = useCallback((updated) => {
    setTracks((previous) =>
      previous.map((track) => (track.id === updated.id ? updated : track)),
    );
  }, []);

  // The edit modal lives at the app shell, with no handle on whichever feed
  // is mounted; it announces saves and any live feed patches itself.
  useEffect(() => {
    const handleTrackUpdated = (event) => {
      if (event.detail?.id) {
        replaceTrack(event.detail);
      }
    };

    window.addEventListener(TRACK_UPDATED_EVENT, handleTrackUpdated);
    return () => window.removeEventListener(TRACK_UPDATED_EVENT, handleTrackUpdated);
  }, [replaceTrack]);

  return {
    tracks,
    total,
    isLoading,
    isLoadingMore,
    hasMore,
    error,
    loadMore,
    replaceTrack,
  };
}
