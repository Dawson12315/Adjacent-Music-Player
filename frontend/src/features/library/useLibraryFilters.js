import { useMemo } from "react";

import { useLibrary } from "../../contexts/LibraryContext";
import { useNavigation } from "../../hooks/useNavigation";

/**
 * Derives the visible slice of the library from the current route and search term.
 *
 * Filtering stays client-side, matching the previous behaviour: search covers genre as
 * well as title/artist/album and needs no round trip. The backend does support server-side
 * search and pagination, and moving to it would cut the startup payload considerably, but
 * it would also change what a search matches — worth doing on its own, not as a side
 * effect of this refactor.
 */
export function useLibraryFilters() {
  const { tracks, artists, albums, genres } = useLibrary();
  const { selectedArtist, selectedAlbum, selectedGenre, searchQuery } = useNavigation();

  const query = searchQuery.trim().toLowerCase();

  const visibleTracks = useMemo(() => {
    return tracks.filter((track) => {
      const matchesArtist = selectedArtist
        ? track.artists?.includes(selectedArtist) || track.artist === selectedArtist
        : true;

      const matchesAlbum = selectedAlbum ? track.album === selectedAlbum : true;

      const matchesGenre = selectedGenre
        ? (track.genres || []).includes(selectedGenre)
        : true;

      const matchesSearch =
        query === "" ||
        track.title?.toLowerCase().includes(query) ||
        track.artist?.toLowerCase().includes(query) ||
        track.album?.toLowerCase().includes(query) ||
        track.genre?.toLowerCase().includes(query);

      return matchesArtist && matchesAlbum && matchesGenre && matchesSearch;
    });
  }, [tracks, selectedArtist, selectedAlbum, selectedGenre, query]);

  const visibleArtists = useMemo(
    () => artists.filter((artist) => artist.toLowerCase().includes(query)),
    [artists, query],
  );

  const visibleAlbums = useMemo(
    () => albums.filter((album) => album.toLowerCase().includes(query)),
    [albums, query],
  );

  const visibleGenres = useMemo(
    () => genres.filter((genre) => genre.toLowerCase().includes(query)),
    [genres, query],
  );

  const genreCounts = useMemo(() => {
    const counts = new Map();

    tracks.forEach((track) => {
      (track.genres || []).forEach((genre) => {
        counts.set(genre, (counts.get(genre) || 0) + 1);
      });
    });

    return counts;
  }, [tracks]);

  return { visibleTracks, visibleArtists, visibleAlbums, visibleGenres, genreCounts };
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
