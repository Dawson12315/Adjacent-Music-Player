import { apiClient } from "./apiClient";

/**
 * The server-side playback session is what lets playback resume after a reload.
 *
 * Two things constrain how this is called: every field is required (a partial PUT is a
 * 422), and each PUT deletes and re-inserts the whole queue — so writes must be
 * debounced rather than fired on every progress tick.
 */

/** Side effect: creates the session row if the user does not have one yet. */
export async function getPlaybackState(options) {
  const data = await apiClient.get("/api/playback", options);

  return {
    currentTrackId: data.current_track_id,
    queueIndex: data.queue_index,
    currentTimeSeconds: data.current_time_seconds,
    isPlaying: data.is_playing,
    isShuffle: data.is_shuffle,
    isLoop: data.is_loop,
    queueTrackIds: data.queue_track_ids || [],
  };
}

export function savePlaybackState({
  currentTrackId,
  queueIndex,
  currentTimeSeconds,
  isPlaying,
  isShuffle,
  isLoop,
  queueTrackIds,
}) {
  return apiClient.put("/api/playback", {
    current_track_id: currentTrackId ?? null,
    queue_index: queueIndex,
    // The column is an integer; sending a float is rejected.
    current_time_seconds: Math.max(0, Math.floor(currentTimeSeconds || 0)),
    is_playing: isPlaying,
    is_shuffle: isShuffle,
    is_loop: isLoop,
    queue_track_ids: queueTrackIds,
  });
}
