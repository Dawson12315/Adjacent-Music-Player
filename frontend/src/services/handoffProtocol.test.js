import { describe, expect, it } from "vitest";

import {
  claimFrame,
  commandFrame,
  handoffSocketUrl,
  helloFrame,
  interpolatedPosition,
  readServerFrame,
  reportFrame,
  stateFrame,
  transferFrame,
} from "./handoffProtocol";
import { browserNameFrom } from "./deviceIdentity";

describe("the browser name", () => {
  it("reads browser and OS from the user agent", () => {
    expect(browserNameFrom("Mozilla/5.0 (Macintosh) Chrome/120.0", "MacIntel")).toBe("Chrome on Mac");
    expect(browserNameFrom("Mozilla/5.0 (Windows NT 10) Firefox/121.0", "Win32")).toBe("Firefox on Windows");
    expect(browserNameFrom("Mozilla/5.0 (iPad) Version/17 Safari/605", "")).toBe("Safari on iPad");
    expect(browserNameFrom("Mozilla/5.0 Edg/120.0", "Linux x86_64")).toBe("Edge on Linux");
  });
});

describe("the frames", () => {
  const device = { deviceId: "d1", name: "Chrome on Mac", kind: "web", platform: "MacIntel", appVersion: "web" };

  it("says hello with the identity", () => {
    expect(helloFrame(device)).toMatchObject({ type: "hello", device_id: "d1", kind: "web" });
  });

  it("caps and cleans the queue in a state frame", () => {
    const big = Array.from({ length: 6000 }, (_, i) => i + 1);
    const frame = stateFrame({ trackId: 5, queue: big, index: 10, position: 12.7, playing: true, loop: true });
    expect(frame.queue_track_ids.length).toBe(5000);
    expect(frame.current_time_seconds).toBe(13);
    expect(frame.is_loop).toBe(true);
  });

  it("wraps claim, report, transfer and command", () => {
    expect(claimFrame({ a: 1 })).toEqual({ type: "claim", state: { a: 1 } });
    expect(reportFrame({ trackId: 3, index: 2, position: 4, playing: true, version: 7 })).toMatchObject({
      type: "state",
      current_track_id: 3,
      version: 7,
    });
    expect(transferFrame("d2", { a: 1 })).toEqual({ type: "transfer", to: "d2", state: { a: 1 } });
    expect(transferFrame("d2", null)).toEqual({ type: "transfer", to: "d2" });
    expect(commandFrame("pause").action).toBe("pause");
    expect(() => commandFrame("explode")).toThrow();
  });
});

describe("reading a server frame", () => {
  it("flags whether the lease is this device", () => {
    expect(readServerFrame({ type: "lease", active_device_id: "me" }, "me").isActiveHere).toBe(true);
    expect(readServerFrame({ type: "lease", active_device_id: "other" }, "me").isActiveHere).toBe(false);
  });

  it("passes take_over and command through, and ignores unknowns and pings", () => {
    expect(readServerFrame({ type: "take_over", state: { x: 1 } }, "me").kind).toBe("take_over");
    expect(readServerFrame({ type: "command", action: "next" }, "me")).toMatchObject({ kind: "command", action: "next" });
    expect(readServerFrame({ type: "ping" }, "me")).toBeNull();
  });
});

describe("the remote clock", () => {
  it("advances a playing remote and holds a paused one", () => {
    expect(interpolatedPosition({ position: 10, reportedAtMs: 1000, playing: true }, 4000)).toBeCloseTo(13, 1);
    expect(interpolatedPosition({ position: 10, reportedAtMs: 1000, playing: false }, 4000)).toBe(10);
  });
});

describe("the socket url", () => {
  it("becomes ws or wss with the handoff path", () => {
    expect(handoffSocketUrl("http://localhost:8000")).toBe("ws://localhost:8000/api/playback/ws");
    expect(handoffSocketUrl("https://music.example.com/")).toBe("wss://music.example.com/api/playback/ws");
  });
});
