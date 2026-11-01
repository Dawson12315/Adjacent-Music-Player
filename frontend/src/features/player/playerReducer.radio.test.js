import { describe, expect, it } from "vitest";

import { initialPlayerState, playerReducer } from "./playerReducer";

const t = (id, artist = "Someone") => ({ id, title: `Song ${id}`, artist });

function playing(tracks, index) {
  return { ...initialPlayerState, queue: tracks, originalQueue: tracks, queueIndex: index, currentTrack: tracks[index] };
}

describe("a station's batches in the queue", () => {
  it("appends a batch behind what is queued, in order, without repeats", () => {
    const state = playing([t(1), t(2), t(3)], 1);
    const next = playerReducer(state, { type: "APPEND_TRACKS", tracks: [t(3), t(4), t(5), t(4)] });
    expect(next.queue.map((track) => track.id)).toEqual([1, 2, 3, 4, 5]);
    expect(next.originalQueue.map((track) => track.id)).toEqual([1, 2, 3, 4, 5]);
    expect(next.queueIndex).toBe(1);
    expect(next.currentTrack.id).toBe(2);
  });

  it("appends in order even with shuffle on: a station's order is the station's", () => {
    const state = { ...playing([t(1), t(2)], 0), isShuffle: true };
    const next = playerReducer(state, { type: "APPEND_TRACKS", tracks: [t(3), t(4), t(5)] });
    expect(next.queue.map((track) => track.id)).toEqual([1, 2, 3, 4, 5]);
  });

  it("leaves the state alone when nothing new arrives", () => {
    const state = playing([t(1), t(2)], 0);
    expect(playerReducer(state, { type: "APPEND_TRACKS", tracks: [t(1), t(2)] })).toBe(state);
    expect(playerReducer(state, { type: "APPEND_TRACKS", tracks: [] })).toBe(state);
  });

  it("replaces what is up next and keeps what played and what is playing", () => {
    const state = playing([t(1), t(2), t(3), t(4)], 1);
    const next = playerReducer(state, { type: "REPLACE_UPCOMING", tracks: [t(7), t(2), t(8)] });
    expect(next.queue.map((track) => track.id)).toEqual([1, 2, 7, 8]);
    expect(next.queueIndex).toBe(1);
    expect(next.currentTrack.id).toBe(2);
  });

  it("drops upcoming tracks the listener said no to, by id or by artist, and nothing behind", () => {
    const state = playing([t(1, "Fen"), t(2), t(3, "Fen"), t(4, "Other"), t(5, "fen")], 1);
    const byId = playerReducer(state, { type: "REMOVE_UPCOMING", trackIds: [4, 1] });
    expect(byId.queue.map((track) => track.id)).toEqual([1, 2, 3, 5]);
    const byArtist = playerReducer(state, { type: "REMOVE_UPCOMING", artists: ["Fen"] });
    expect(byArtist.queue.map((track) => track.id)).toEqual([1, 2, 4]);
    expect(byArtist.originalQueue.map((track) => track.id)).toEqual([1, 2, 4]);
    expect(byArtist.queueIndex).toBe(1);
    expect(playerReducer(state, { type: "REMOVE_UPCOMING", trackIds: [99] })).toBe(state);
  });
});
