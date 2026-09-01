import { apiClient } from "./apiClient";

/**
 * Listening events drive the stats and recommendation signals. Each endpoint requires a
 * body, so `{}` is the minimum payload.
 *
 * Note that `/like` and `/unlike` only record the event — adding the track to the Liked
 * Songs playlist is a separate call in playlistsService.
 */
function postEvent(trackId, eventPath, payload) {
  return apiClient.post(`/api/tracks/${trackId}/${eventPath}`, {
    source_type: payload.sourceType ?? "library",
    source_id: payload.sourceId ?? null,
    position_seconds: payload.positionSeconds ?? 0,
    duration_seconds: payload.durationSeconds ?? null,
    session_id: payload.sessionId ?? null,
  });
}

export const recordPlayStart = (trackId, payload) =>
  postEvent(trackId, "play-start", payload);

export const recordPlayComplete = (trackId, payload) =>
  postEvent(trackId, "play-complete", payload);

export const recordSkip = (trackId, payload) => postEvent(trackId, "skip", payload);

export const recordLike = (trackId, payload) => postEvent(trackId, "like", payload);

export const recordUnlike = (trackId, payload) => postEvent(trackId, "unlike", payload);
