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
