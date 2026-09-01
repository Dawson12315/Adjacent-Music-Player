import { useMemo } from "react";

import { useLibrary } from "../../contexts/LibraryContext";
import { useNavigation } from "../../hooks/useNavigation";

/**
 * Client-side filtering for the entity name lists.
 *
 * These stay in the browser deliberately: artists, albums and genres are roughly 125 KB
 * of strings combined, so filtering them locally is instant and costs nothing. Tracks are
 * the opposite case and are paged from the server — see useTrackFeed.
 */
export function useLibraryFilters() {
  const { artists, albums, genres } = useLibrary();
  const { searchQuery } = useNavigation();

  const query = searchQuery.trim().toLowerCase();

  const visibleArtists = useMemo(
    () => (query ? artists.filter((a) => a.toLowerCase().includes(query)) : artists),
    [artists, query],
  );

  const visibleAlbums = useMemo(
    () => (query ? albums.filter((a) => a.toLowerCase().includes(query)) : albums),
    [albums, query],
  );

  const visibleGenres = useMemo(
    () => (query ? genres.filter((g) => g.toLowerCase().includes(query)) : genres),
    [genres, query],
  );

  return { visibleArtists, visibleAlbums, visibleGenres };
}

/** Slice a list for the current page and report how many pages there are. */
export function usePagination(items, page, pageSize) {
  return useMemo(() => {
    const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
    const safePage = Math.min(page, totalPages);

    return {
      pageItems: items.slice((safePage - 1) * pageSize, safePage * pageSize),
      totalPages,
      page: safePage,
    };
  }, [items, page, pageSize]);
}
