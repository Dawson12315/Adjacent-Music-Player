import { describe, expect, it, vi } from "vitest";

import { initialPlayerState, playerReducer } from "./playerReducer";

const track = (id) => ({ id, title: `Track ${id}` });
const TRACKS = [track(1), track(2), track(3), track(4), track(5)];

function stateWith(overrides) {
  return { ...initialPlayerState, ...overrides };
}

/** Play track 3 of the five-track list, unshuffled. */
function playingThird() {
  return playerReducer(initialPlayerState, {
    type: "PLAY_TRACK",
    track: TRACKS[2],
    sourceTracks: TRACKS,
  });
}

describe("PLAY_TRACK", () => {
  it("queues the whole list and selects the clicked track", () => {
    const state = playingThird();

    expect(state.currentTrack.id).toBe(3);
    expect(state.queueIndex).toBe(2);
    expect(state.queue.map((item) => item.id)).toEqual([1, 2, 3, 4, 5]);
    expect(state.originalQueue.map((item) => item.id)).toEqual([1, 2, 3, 4, 5]);
  });

  it("keeps played tracks in order and shuffles only what is upcoming", () => {
    // Reverse the upcoming slice so the shuffle is observable.
    vi.spyOn(Math, "random").mockReturnValue(0);

    const state = playerReducer(stateWith({ isShuffle: true }), {
      type: "PLAY_TRACK",
      track: TRACKS[2],
      sourceTracks: TRACKS,
    });

    expect(state.queue.slice(0, 3).map((item) => item.id)).toEqual([1, 2, 3]);
    expect(state.queue.slice(3).map((item) => item.id).sort()).toEqual([4, 5]);
    // The unshuffled order is retained so shuffle can be switched back off.
    expect(state.originalQueue.map((item) => item.id)).toEqual([1, 2, 3, 4, 5]);

    vi.restoreAllMocks();
  });

  it("plays a track that is not in the list on its own", () => {
    const orphan = track(99);

    const state = playerReducer(initialPlayerState, {
      type: "PLAY_TRACK",
      track: orphan,
      sourceTracks: TRACKS,
    });

    expect(state.queue).toEqual([orphan]);
    expect(state.queueIndex).toBe(0);
    expect(state.currentTrack.id).toBe(99);
  });
});

describe("NEXT and PREVIOUS", () => {
  it("advances through the queue", () => {
    const state = playerReducer(playingThird(), { type: "NEXT" });

    expect(state.queueIndex).toBe(3);
    expect(state.currentTrack.id).toBe(4);
  });

  it("stops at the end of the queue rather than wrapping", () => {
    const atEnd = stateWith({
      queue: TRACKS,
      originalQueue: TRACKS,
      queueIndex: 4,
      currentTrack: TRACKS[4],
    });

    expect(playerReducer(atEnd, { type: "NEXT" })).toBe(atEnd);
  });

  it("steps backwards", () => {
    const state = playerReducer(playingThird(), { type: "PREVIOUS" });

    expect(state.queueIndex).toBe(1);
    expect(state.currentTrack.id).toBe(2);
  });

  it("does not step back past the first track", () => {
    const atStart = stateWith({
      queue: TRACKS,
      originalQueue: TRACKS,
      queueIndex: 0,
      currentTrack: TRACKS[0],
    });

    expect(playerReducer(atStart, { type: "PREVIOUS" })).toBe(atStart);
  });
});

describe("TOGGLE_SHUFFLE", () => {
  it("restores the original order and re-finds the playing track", () => {
    // Shuffled queue where the playing track sits at a different index than originally.
    const shuffled = stateWith({
      isShuffle: true,
      queue: [TRACKS[2], TRACKS[4], TRACKS[0], TRACKS[3], TRACKS[1]],
      originalQueue: TRACKS,
      queueIndex: 1,
      currentTrack: TRACKS[4],
    });

    const state = playerReducer(shuffled, { type: "TOGGLE_SHUFFLE" });

    expect(state.isShuffle).toBe(false);
    expect(state.queue.map((item) => item.id)).toEqual([1, 2, 3, 4, 5]);
    // Track 5 lives at index 4 in the original order.
    expect(state.queueIndex).toBe(4);
  });

  it("toggles without touching an empty queue", () => {
    const state = playerReducer(initialPlayerState, { type: "TOGGLE_SHUFFLE" });

    expect(state.isShuffle).toBe(true);
    expect(state.queue).toEqual([]);
  });
});

describe("REMOVE_AT", () => {
  it("removing an upcoming track leaves the current index alone", () => {
    const state = playerReducer(playingThird(), { type: "REMOVE_AT", index: 4 });

    expect(state.queue.map((item) => item.id)).toEqual([1, 2, 3, 4]);
    expect(state.queueIndex).toBe(2);
    expect(state.currentTrack.id).toBe(3);
  });

  it("removing an already-played track shifts the current index back", () => {
    const state = playerReducer(playingThird(), { type: "REMOVE_AT", index: 0 });

    expect(state.queue.map((item) => item.id)).toEqual([2, 3, 4, 5]);
    expect(state.queueIndex).toBe(1);
    expect(state.queue[state.queueIndex].id).toBe(3);
  });

  it("removing the playing track falls through to the next one", () => {
    const state = playerReducer(playingThird(), { type: "REMOVE_AT", index: 2 });

    expect(state.queue.map((item) => item.id)).toEqual([1, 2, 4, 5]);
    expect(state.queueIndex).toBe(2);
    expect(state.currentTrack.id).toBe(4);
  });

  it("clears the player when the last remaining track is removed", () => {
    const single = stateWith({
      queue: [TRACKS[0]],
      originalQueue: [TRACKS[0]],
      queueIndex: 0,
      currentTrack: TRACKS[0],
    });

    const state = playerReducer(single, { type: "REMOVE_AT", index: 0 });

    expect(state.queue).toEqual([]);
    expect(state.queueIndex).toBe(-1);
    expect(state.currentTrack).toBeNull();
  });

  it("ignores an index that is not in the queue", () => {
    const before = playingThird();

    expect(playerReducer(before, { type: "REMOVE_AT", index: 99 })).toBe(before);
  });
});

describe("RESTORE and REPLACE_TRACK", () => {
  it("rehydrates a saved session", () => {
    const state = playerReducer(initialPlayerState, {
      type: "RESTORE",
      queue: TRACKS,
      queueIndex: 3,
      currentTrack: TRACKS[3],
      isShuffle: true,
      isLoop: true,
    });

    expect(state.queueIndex).toBe(3);
    expect(state.currentTrack.id).toBe(4);
    expect(state.isShuffle).toBe(true);
    expect(state.isLoop).toBe(true);
  });

  it("applies an edited track everywhere it is referenced", () => {
    const edited = { id: 3, title: "Renamed" };
    const state = playerReducer(playingThird(), { type: "REPLACE_TRACK", track: edited });

    expect(state.currentTrack.title).toBe("Renamed");
    expect(state.queue[2].title).toBe("Renamed");
    expect(state.originalQueue[2].title).toBe("Renamed");
  });
});

describe("ADD_TO_QUEUE", () => {
  it("appends to both the live and original queues", () => {
    const extra = track(6);
    const state = playerReducer(playingThird(), { type: "ADD_TO_QUEUE", track: extra });

    expect(state.queue.at(-1).id).toBe(6);
    expect(state.originalQueue.at(-1).id).toBe(6);
  });
});
