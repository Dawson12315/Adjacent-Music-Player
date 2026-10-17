/**
 * What a row says under a title.
 *
 * A track credits everyone on it: the lead and whoever was featured. The row
 * used to show the first credit only, which made a one-feature guest's page
 * look like a parsing error ("The Walk" by Ying Yang Twins, filed under
 * "BG"). The credits come from the server as `artists`; `artist` stays the
 * lead for sorting, grouping and the artist page.
 */
export function creditLine(track) {
  const credits = Array.isArray(track?.artists) ? track.artists.filter(Boolean) : [];

  if (credits.length > 0) return credits.join(", ");

  return track?.artist || "Unknown Artist";
}

/** The artist a track's record is filed under: the album artist when the file names one. */
export function recordArtist(track) {
  return track?.album_artist || track?.artist || null;
}
