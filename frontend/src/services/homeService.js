import { apiClient } from "./apiClient";
import { normalizeTracks } from "./normalize";

/**
 * Personalised recommendations, seeded server-side from the user's own listening rather
 * than from a playlist. Returns an empty list for someone with no history yet.
 *
 * This runs the full retrieval pipeline, so it is slow enough to want a skeleton.
 */
export async function getForYou({ limit = 20, signal } = {}) {
  const data = await apiClient.get("/api/recommendations/for-you", {
    params: { limit },
    signal,
  });

  return normalizeTracks(data, { metadataComplete: true });
}
