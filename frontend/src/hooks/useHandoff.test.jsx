import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useHandoff } from "./useHandoff";

// Drive the socket by hand.
let socketHandle;
vi.mock("../services/handoffSocket", () => ({
  createDeviceSocket: ({ onFrame, onStatus }) => {
    socketHandle = { onFrame, onStatus, sent: [] };
    onStatus?.("open");
    return {
      send: (frame) => {
        socketHandle.sent.push(frame);
        return true;
      },
      close: () => {},
      getStatus: () => "open",
    };
  },
}));

vi.mock("../services/deviceIdentity", () => ({
  describeDevice: () => ({ deviceId: "me", name: "Chrome on Mac", kind: "web", platform: "web", appVersion: "web" }),
}));

vi.mock("../services/healthService", () => ({
  getHealth: async () => ({ apiVersion: 8, capabilities: ["device-handoff"], sessionDays: 30 }),
}));

vi.mock("../services/handoffHttp", () => ({
  sayHello: vi.fn(),
  getDevices: vi.fn(),
  claim: vi.fn(),
  report: vi.fn(),
  transfer: vi.fn(),
  command: vi.fn(),
}));

function deps(overrides = {}) {
  return {
    currentUser: { id: 1 },
    getStateSnapshot: () => ({ trackId: 7, queue: [7, 8], index: 0, position: 3, playing: true, shuffle: false, loop: false, source: {} }),
    pauseForRemote: vi.fn(),
    takeOver: vi.fn(),
    runCommand: vi.fn(),
    ...overrides,
  };
}

async function mountReady(overrides = {}) {
  const d = deps(overrides);
  const view = renderHook((props) => useHandoff(props), { initialProps: d });
  await waitFor(() => expect(view.result.current.available).toBe(true));
  await waitFor(() => expect(view.result.current.me?.deviceId).toBe("me"));
  return { view, d };
}

beforeEach(() => {
  socketHandle = undefined;
});
afterEach(() => {
  vi.clearAllMocks();
});

describe("useHandoff (web)", () => {
  it("is inert without the capability", async () => {
    vi.resetModules();
    const view = renderHook((props) => useHandoff(props), { initialProps: deps({ currentUser: null }) });
    expect(view.result.current.available).toBe(false);
  });

  it("turns on when the server advertises handoff and opens a socket", async () => {
    await mountReady();
    expect(socketHandle).toBeTruthy();
  });

  it("goes remote and pauses when another device takes the lease", async () => {
    const { view, d } = await mountReady();
    act(() => {
      socketHandle.onFrame({
        type: "lease",
        active_device_id: "phone",
        active_device_name: "Dawson's iPhone",
        state: { is_playing: true, current_time_seconds: 20, current_track_id: 7 },
      });
    });
    expect(d.pauseForRemote).toHaveBeenCalled();
    expect(view.result.current.isActiveHere).toBe(false);
    expect(view.result.current.activeName).toBe("Dawson's iPhone");
    expect(view.result.current.remote?.playing).toBe(true);
  });

  it("claims by sending a claim frame", async () => {
    const { view } = await mountReady();
    act(() => view.result.current.claim());
    expect(socketHandle.sent.some((f) => f.type === "claim")).toBe(true);
    expect(view.result.current.isActiveHere).toBe(true);
  });

  it("hands a take_over to the player", async () => {
    const { d } = await mountReady();
    act(() => socketHandle.onFrame({ type: "take_over", state: { queue_track_ids: [7], queue_index: 0 } }));
    expect(d.takeOver).toHaveBeenCalledWith({ queue_track_ids: [7], queue_index: 0 });
  });
});
