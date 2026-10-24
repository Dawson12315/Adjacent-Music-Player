import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAudioElement } from "./useAudioElement";

/** A stand-in for the <audio> element: records loads and plays. */
function fakeAudio() {
  return {
    src: "",
    error: null,
    volume: 1,
    muted: false,
    load: vi.fn(),
    play: vi.fn(() => Promise.resolve()),
    pause: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
}

function mount(initial) {
  const audio = fakeAudio();
  const hook = renderHook((props) => useAudioElement(props), { initialProps: initial });
  act(() => {
    hook.result.current.audioRef.current = audio;
  });
  return { audio, hook };
}

afterEach(() => vi.restoreAllMocks());

describe("useAudioElement and the lease hold", () => {
  it("neither loads nor plays while the source is held", () => {
    const { audio, hook } = mount({ track: { id: 1 }, isPlaying: true, volume: 1, isMuted: false, holdSource: true });
    // Re-render so the effects see the ref.
    hook.rerender({ track: { id: 1 }, isPlaying: true, volume: 1, isMuted: false, holdSource: true });

    expect(audio.load).not.toHaveBeenCalled();
    expect(audio.play).not.toHaveBeenCalled();
  });

  it("loads and plays once the hold lifts", () => {
    const { audio, hook } = mount({ track: { id: 1 }, isPlaying: true, volume: 1, isMuted: false, holdSource: true });
    hook.rerender({ track: { id: 1 }, isPlaying: true, volume: 1, isMuted: false, holdSource: false });

    expect(audio.load).toHaveBeenCalledTimes(1);
    expect(audio.play).toHaveBeenCalledTimes(1);
  });

  it("does not press play on the previous track when the bar moves on under a hold", () => {
    const { audio, hook } = mount({ track: { id: 1 }, isPlaying: true, volume: 1, isMuted: false, holdSource: false });
    hook.rerender({ track: { id: 1 }, isPlaying: true, volume: 1, isMuted: false, holdSource: false });
    audio.load.mockClear();
    audio.play.mockClear();

    // Another device takes the lease, then the user presses Next here.
    hook.rerender({ track: { id: 1 }, isPlaying: true, volume: 1, isMuted: false, holdSource: true });
    hook.rerender({ track: { id: 2 }, isPlaying: true, volume: 1, isMuted: false, holdSource: true });

    expect(audio.load).not.toHaveBeenCalled();
    expect(audio.play).not.toHaveBeenCalled();
  });
});

describe("useAudioElement never plays an empty element", () => {
  it("attaches the source before play when the element has none", () => {
    // The track arrives while the lease is unknown; the hold lifts in the
    // same render as the play. Whatever the order, play() must find a src.
    const { audio, hook } = mount({ track: { id: 7 }, isPlaying: true, volume: 1, isMuted: false, holdSource: true });
    hook.rerender({ track: { id: 7 }, isPlaying: true, volume: 1, isMuted: false, holdSource: true });
    expect(audio.src).toBe("");

    hook.rerender({ track: { id: 7 }, isPlaying: true, volume: 1, isMuted: false, holdSource: false });
    expect(audio.src).toContain("/api/tracks/7/stream");
    expect(audio.load).toHaveBeenCalled();
    expect(audio.play).toHaveBeenCalled();
    expect(hook.result.current.hasSource()).toBe(true);
  });

  it("re-points an element something emptied, without reloading one that is fine", () => {
    // Mounted held, so the lift is a dependency change the effects see.
    const { audio, hook } = mount({ track: { id: 3 }, isPlaying: false, volume: 1, isMuted: false, holdSource: true });
    hook.rerender({ track: { id: 3 }, isPlaying: false, volume: 1, isMuted: false, holdSource: false });
    expect(audio.load).toHaveBeenCalledTimes(1);

    // A pause/resume on a loaded element is not a reload: the position would go.
    hook.rerender({ track: { id: 3 }, isPlaying: true, volume: 1, isMuted: false, holdSource: false });
    expect(audio.load).toHaveBeenCalledTimes(1);
    expect(audio.play).toHaveBeenCalledTimes(1);

    // The element lost its source behind the hook's back (a fresh element,
    // a reset): the next play attaches it again.
    audio.src = "";
    hook.rerender({ track: { id: 3 }, isPlaying: false, volume: 1, isMuted: false, holdSource: false });
    hook.rerender({ track: { id: 3 }, isPlaying: true, volume: 1, isMuted: false, holdSource: false });
    expect(audio.src).toContain("/api/tracks/3/stream");
    expect(audio.load).toHaveBeenCalledTimes(2);
  });

  it("reports no source until one is attached", () => {
    const { hook } = mount({ track: null, isPlaying: false, volume: 1, isMuted: false, holdSource: false });
    expect(hook.result.current.hasSource()).toBe(false);
  });
});
