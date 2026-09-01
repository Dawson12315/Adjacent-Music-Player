import { apiClient } from "./apiClient";

/** Bare string array of distinct genre names. */
export function listGenres(options) {
  return apiClient.get("/api/genres", options);
}
