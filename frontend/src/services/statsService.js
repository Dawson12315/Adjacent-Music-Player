import { apiClient } from "./apiClient";
import { normalizeTracks } from "./normalize";

/**
 * Stats tracks carry genres and artists but never artwork, so the UI resolves artwork
 * from the shared album cache instead.
 */
export async function getStatsOverview(options) {
  const data = await apiClient.get("/api/stats/overview", options);

  return {
    top_played: normalizeTracks(data.top_played, { metadataComplete: true }),
    most_liked: normalizeTracks(data.most_liked, { metadataComplete: true }),
    most_skipped: normalizeTracks(data.most_skipped, { metadataComplete: true }),
    recently_played: normalizeTracks(data.recently_played, { metadataComplete: true }),
    top_genres: data.top_genres || [],
  };
}
