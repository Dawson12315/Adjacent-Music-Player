/**
 * The backend writes the system playlist's key as `liked_songs:{user_id}`; the bare
 * string `liked_songs` is a legacy value that migrations move off. Every check goes
 * through this helper — four separate sort implementations previously existed, three of
 * them comparing against the legacy literal, so the pinned playlist silently dropped to
 * alphabetical order after any playlist edit.
 */
export function isLikedSongsPlaylist(playlist) {
  return Boolean(playlist?.system_key?.startsWith("liked_songs:"));
}

/** System playlist first, everything else alphabetical. */
export function sortPlaylistsWithSystemFirst(items) {
  return [...items].sort((a, b) => {
    const aSystem = isLikedSongsPlaylist(a) ? 0 : 1;
    const bSystem = isLikedSongsPlaylist(b) ? 0 : 1;

    if (aSystem !== bSystem) {
      return aSystem - bSystem;
    }

    return (a.name || "").localeCompare(b.name || "");
  });
}

/** Insert or replace a playlist while keeping the pinned ordering. */
export function upsertPlaylist(playlists, playlist) {
  const exists = playlists.some((item) => item.id === playlist.id);

  const next = exists
    ? playlists.map((item) => (item.id === playlist.id ? playlist : item))
    : [...playlists, playlist];

  return sortPlaylistsWithSystemFirst(next);
}
