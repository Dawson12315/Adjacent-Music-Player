import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

/**
 * jsdom implements no media playback, so the audio element's imperative API has to be
 * stubbed for anything that touches the player to run under test.
 */
Object.defineProperty(window.HTMLMediaElement.prototype, "play", {
  configurable: true,
  value: vi.fn().mockResolvedValue(undefined),
});

Object.defineProperty(window.HTMLMediaElement.prototype, "pause", {
  configurable: true,
  value: vi.fn(),
});

Object.defineProperty(window.HTMLMediaElement.prototype, "load", {
  configurable: true,
  value: vi.fn(),
});

// react-window measures its container; jsdom has no layout engine.
if (!("ResizeObserver" in window)) {
  window.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// Media Session and object URLs are likewise unimplemented in jsdom.
if (!("MediaMetadata" in window)) {
  window.MediaMetadata = class MediaMetadata {
    constructor(init) {
      Object.assign(this, init);
    }
  };
}

if (!window.URL.createObjectURL) {
  window.URL.createObjectURL = vi.fn(() => "blob:mock");
  window.URL.revokeObjectURL = vi.fn();
}
