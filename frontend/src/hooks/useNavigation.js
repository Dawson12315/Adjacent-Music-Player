import { useCallback, useMemo } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

/**
 * Navigation state, derived from the URL rather than duplicated in React state.
 *
 * Views used to be a single `activeView` string with four filter slots, cleared by five
 * repeated setState calls at six different call sites. Now the route is the state: the
 * view and the current artist/album/genre/playlist selection all read off the URL, so
 * they cannot drift out of sync, and views are linkable and survive a reload.
 *
 * Names are encoded when building paths and decoded by the router on the way back, which
 * is what lets artists like "AC/DC" round-trip.
 */
export function buildArtistPath(name) {
  return `/artists/${encodeURIComponent(name)}`;
}

export function buildAlbumPath(name) {
  return `/albums/${encodeURIComponent(name)}`;
}

export function buildGenrePath(name) {
  return `/genres/${encodeURIComponent(name)}`;
}

export function buildPlaylistPath(playlistId) {
  return `/playlists/${playlistId}`;
}

/**
 * Parsed from the pathname rather than from `useParams`, because route params only
 * accumulate downwards: a layout component rendering the sidebar and header sits above
 * the route that declares `:name`, so it would never see it. Parsing here means every
 * component reads the same navigation state regardless of where it sits in the tree.
 */
function parseLocation(pathname) {
  const [section, rawName] = pathname.split("/").filter(Boolean);
  const name = rawName ? decodeURIComponent(rawName) : null;

  switch (section) {
    case undefined:
      return { activeView: "home" };
    case "tracks":
      return { activeView: "tracks" };
    case "settings":
      return { activeView: "settings" };
    case "insights":
      return { activeView: "insights" };
    case "playlists":
      return { activeView: "playlist", selectedPlaylistId: name ? Number(name) : null };
    case "artists":
      return name
        ? { activeView: "tracks", selectedArtist: name }
        : { activeView: "artists" };
    case "albums":
      return name ? { activeView: "tracks", selectedAlbum: name } : { activeView: "albums" };
    case "genres":
      return name ? { activeView: "tracks", selectedGenre: name } : { activeView: "genres" };
    default:
      return { activeView: "home" };
  }
}

export function useNavigation() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  const {
    activeView,
    selectedArtist = null,
    selectedAlbum = null,
    selectedGenre = null,
    selectedPlaylistId = null,
  } = parseLocation(pathname);

  const searchQuery = searchParams.get("q") || "";
  const page = Math.max(1, Number(searchParams.get("page") || 1));

  const setSearchQuery = useCallback(
    (value) => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous);

          if (value) {
            next.set("q", value);
          } else {
            next.delete("q");
          }

          // A new search always returns to the first page.
          next.delete("page");
          return next;
        },
        // Typing should not push a history entry per keystroke.
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setPage = useCallback(
    (value) => {
      setSearchParams((previous) => {
        const next = new URLSearchParams(previous);

        if (value > 1) {
          next.set("page", String(value));
        } else {
          next.delete("page");
        }

        return next;
      });
    },
    [setSearchParams],
  );

  const goToArtist = useCallback((name) => navigate(buildArtistPath(name)), [navigate]);
  const goToAlbum = useCallback((name) => navigate(buildAlbumPath(name)), [navigate]);
  const goToGenre = useCallback((name) => navigate(buildGenrePath(name)), [navigate]);
  const goToPlaylist = useCallback(
    (playlistId) => navigate(buildPlaylistPath(playlistId)),
    [navigate],
  );
  const clearFilters = useCallback(() => navigate("/tracks"), [navigate]);
  const goHome = useCallback(() => navigate("/"), [navigate]);

  return useMemo(
    () => ({
      activeView,
      selectedArtist,
      selectedAlbum,
      selectedGenre,
      selectedPlaylistId,
      searchQuery,
      setSearchQuery,
      page,
      setPage,
      goToArtist,
      goToAlbum,
      goToGenre,
      goToPlaylist,
      clearFilters,
      goHome,
      navigate,
    }),
    [
      activeView,
      selectedArtist,
      selectedAlbum,
      selectedGenre,
      selectedPlaylistId,
      searchQuery,
      setSearchQuery,
      page,
      setPage,
      goToArtist,
      goToAlbum,
      goToGenre,
      goToPlaylist,
      clearFilters,
      goHome,
      navigate,
    ],
  );
}
