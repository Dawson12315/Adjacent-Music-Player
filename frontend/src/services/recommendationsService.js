import { apiClient } from "./apiClient";
import { normalizeTrack } from "./normalize";

/**
 * With `debug=true` the response is an object whose `recommendations` entries pair a
 * track with an explanation; without it, a bare array. The app always asks for debug
 * output because the UI shows the reason line under each suggestion.
 *
 * This endpoint is slow — it runs the full retrieval pipeline — so it should never sit
 * on a render path without a loading state.
 */
export async function getPlaylistRecommendations(playlistId, { refresh = 0, signal } = {}) {
  const data = await apiClient.get(`/api/playlists/${playlistId}/recommendations`, {
    params: { debug: true, refresh },
    signal,
  });

  const recommendations = data?.recommendations || [];

  return recommendations
    .map((item) => {
      const track = normalizeTrack(item.track, { metadataComplete: false });

      if (!track) {
        return null;
      }

      return { ...track, debug: item.debug || {} };
    })
    .filter(Boolean);
}
