import { beforeEach, describe, expect, it, vi } from "vitest";

const put = vi.fn(() => Promise.resolve({}));
const get = vi.fn();
vi.mock("./apiClient", () => ({ apiClient: { put: (...a) => put(...a), get: (...a) => get(...a) } }));

import { getPlaybackState, savePlaybackState } from "./playbackService";

const base = { currentTrackId: 1, queueIndex: 0, currentTimeSeconds: 12.7, isPlaying: true, isShuffle: false, isLoop: false, queueTrackIds: [1, 2] };

describe("the playback session and its source", () => {
  beforeEach(() => {
    put.mockClear();
    get.mockReset();
  });

  it("names the source on a save that has one, and says nothing when it has none", async () => {
    await savePlaybackState({ ...base, sourceType: "radio", sourceId: 4 });
    expect(put.mock.calls[0][1]).toMatchObject({ source_type: "radio", source_id: 4, current_time_seconds: 12 });

    await savePlaybackState(base);
    expect(put.mock.calls[1][1]).not.toHaveProperty("source_type");
  });

  it("reads the source back with the session", async () => {
    get.mockResolvedValue({ current_track_id: 9, queue_index: 2, current_time_seconds: 5, is_playing: false, is_shuffle: false, is_loop: false, queue_track_ids: [9], source_type: "radio", source_id: 4 });
    const saved = await getPlaybackState();
    expect(saved).toMatchObject({ currentTrackId: 9, sourceType: "radio", sourceId: 4 });
  });
});
