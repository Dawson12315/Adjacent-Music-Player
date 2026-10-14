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
    // claim is async now (it waits for the HTTP claim when taking over).
    await act(async () => {
      await view.result.current.claim();
    });
    expect(socketHandle.sent.some((f) => f.type === "claim")).toBe(true);
    expect(view.result.current.isActiveHere).toBe(true);
  });

  it("hands a take_over to the player", async () => {
    const { d } = await mountReady();
    act(() => socketHandle.onFrame({ type: "take_over", state: { queue_track_ids: [7], queue_index: 0 } }));
    expect(d.takeOver).toHaveBeenCalledWith({ queue_track_ids: [7], queue_index: 0 });
  });

  it("does not pause when the lease comes back spare after a reconnect", async () => {
    const { view, d } = await mountReady();
    await act(async () => {
      await view.result.current.claim();
    });
    act(() => {
      socketHandle.onFrame({ type: "devices", devices: [], lease: { active_device_id: null, stale: false, state: null } });
    });
    expect(d.pauseForRemote).not.toHaveBeenCalled();
    expect(view.result.current.remote).toBeNull();
  });

  it("does not pause for a holder that has gone quiet", async () => {
    const { d } = await mountReady();
    act(() => {
      socketHandle.onFrame({ type: "lease", active_device_id: "other", active_device_name: "Old Phone", stale: true, state: null });
    });
    expect(d.pauseForRemote).not.toHaveBeenCalled();
  });

  it("ignores a lease reading older than its own claim", async () => {
    const { view, d } = await mountReady();
    await act(async () => {
      await view.result.current.claim();
    });
    act(() => {
      socketHandle.onFrame({ type: "lease", active_device_id: "other", active_device_name: "Phone", state: { is_playing: true } });
    });
    expect(d.pauseForRemote).not.toHaveBeenCalled();
    expect(view.result.current.isActiveHere).toBe(true);
  });

  it("waits for the HTTP claim when taking the music from another device", async () => {
    const http = await import("../services/handoffHttp");
    let resolveClaim;
    http.claim.mockImplementation(() => new Promise((resolve) => { resolveClaim = resolve; }));
    const { view } = await mountReady();
    act(() => {
      socketHandle.onFrame({ type: "lease", active_device_id: "other", active_device_name: "Phone", state: { is_playing: true } });
    });

    let settled = false;
    let claimPromise;
    act(() => {
      claimPromise = view.result.current.claim({ trackId: 9, position: 0, playing: true }).then(() => { settled = true; });
    });
    expect(settled).toBe(false);
    expect(http.claim).toHaveBeenCalledWith("me", expect.objectContaining({ current_track_id: 9 }));
    await act(async () => {
      resolveClaim({ ok: true });
      await claimPromise;
    });
    expect(settled).toBe(true);
    expect(view.result.current.isActiveHere).toBe(true);
  });

  it("marks itself the holder on a take_over, before the player loads it", async () => {
    const { view, d } = await mountReady();
    act(() => {
      socketHandle.onFrame({ type: "take_over", state: { queue_track_ids: [7], queue_index: 0, is_playing: true } });
    });
    expect(d.takeOver).toHaveBeenCalled();
    expect(view.result.current.isActiveHere).toBe(true);
    expect(view.result.current.remote).toBeNull();
  });

  it("surfaces a server error frame", async () => {
    const onError = vi.fn();
    await mountReady({ onError });
    act(() => {
      socketHandle.onFrame({ type: "error", code: "device_away", message: "Dawson's iPhone is not reachable right now." });
    });
    expect(onError).toHaveBeenCalledWith({ code: "device_away", message: "Dawson's iPhone is not reachable right now." });
  });

  it("follows the holder's shuffle and repeat from its ticks", async () => {
    const { view } = await mountReady();
    act(() => {
      socketHandle.onFrame({ type: "lease", active_device_id: "phone", active_device_name: "Phone", state: { is_playing: true, is_shuffle: false, is_loop: false } });
    });
    act(() => {
      socketHandle.onFrame({ type: "state", current_time_seconds: 40, is_playing: true, is_shuffle: true, is_loop: true });
    });
    expect(view.result.current.remote).toMatchObject({ position: 40, shuffle: true, loop: true });
  });

  it("obeys a later claim by another device even right after its own", async () => {
    const { view, d } = await mountReady();
    act(() => {
      socketHandle.onFrame({ type: "lease", active_device_id: null, state: { version: 500 } });
    });
    await act(async () => {
      await view.result.current.claim();
    });
    act(() => {
      socketHandle.onFrame({ type: "lease", active_device_id: "phone", active_device_name: "Phone", state: { is_playing: true, version: 400 } });
    });
    expect(d.pauseForRemote).not.toHaveBeenCalled();
    act(() => {
      socketHandle.onFrame({ type: "lease", active_device_id: "phone", active_device_name: "Phone", state: { is_playing: true, version: 502 } });
    });
    expect(d.pauseForRemote).toHaveBeenCalled();
    expect(view.result.current.isActiveHere).toBe(false);
  });

  it("knows the lease once the first reading arrives, and polls when its socket was replaced", async () => {
    const http = await import("../services/handoffHttp");
    http.getDevices.mockResolvedValue({ devices: [], lease: { active_device_id: null }, pending_commands: [] });
    const { view } = await mountReady();
    expect(view.result.current.leaseKnown).toBe(false);
    act(() => {
      socketHandle.onFrame({ type: "devices", devices: [], lease: { active_device_id: null, state: null } });
    });
    expect(view.result.current.leaseKnown).toBe(true);
    act(() => {
      socketHandle.onStatus("replaced");
    });
    await waitFor(() => expect(http.getDevices).toHaveBeenCalled());
  });
});
