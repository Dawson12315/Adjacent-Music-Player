import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createDeviceSocket, FALLBACK_AFTER_FAILURES, FALLBACK_RETRY_MS, RECONNECT_BACKOFF_MS, REPLACED_CLOSE_CODE } from "./handoffSocket";

class FakeSocket {
  constructor(url) {
    this.url = url;
    this.sent = [];
    FakeSocket.instances.push(this);
  }
  send(data) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    this.closed = true;
  }
  fireOpen() {
    this.onopen?.();
  }
  fireMessage(obj) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
  fireClose(code) {
    this.onclose?.(code == null ? undefined : { code });
  }
}
FakeSocket.instances = [];

const hello = () => ({ type: "hello", device_id: "d1" });

beforeEach(() => {
  FakeSocket.instances = [];
});
afterEach(() => {
  vi.useRealTimers();
});

describe("the handoff socket", () => {
  it("says hello on open and answers a ping with a pong", () => {
    const frames = [];
    const socket = createDeviceSocket({
      url: "ws://x/api/playback/ws",
      hello,
      onFrame: (f) => frames.push(f),
      WebSocketImpl: FakeSocket,
    });
    const ws = FakeSocket.instances[0];
    ws.fireOpen();
    expect(ws.sent[0]).toEqual({ type: "hello", device_id: "d1" });

    ws.fireMessage({ type: "ping" });
    expect(ws.sent[1]).toEqual({ type: "pong" });
    expect(frames).toHaveLength(0);

    ws.fireMessage({ type: "lease", active_device_id: "d1" });
    expect(frames[0]).toMatchObject({ type: "lease" });
    socket.close(false);
  });

  it("falls back after two failed handshakes", () => {
    vi.useFakeTimers();
    const statuses = [];
    createDeviceSocket({
      url: "ws://x/api/playback/ws",
      hello,
      onStatus: (s) => statuses.push(s),
      WebSocketImpl: FakeSocket,
    });
    FakeSocket.instances[0].fireClose();
    vi.runOnlyPendingTimers();
    FakeSocket.instances[1].fireClose();

    expect(statuses).toContain("fallback");
    expect(FakeSocket.instances.length).toBe(FALLBACK_AFTER_FAILURES);
  });

  it("a drop after a successful open is a reconnect, not a fallback", () => {
    vi.useFakeTimers();
    const statuses = [];
    createDeviceSocket({
      url: "ws://x/api/playback/ws",
      hello,
      onStatus: (s) => statuses.push(s),
      WebSocketImpl: FakeSocket,
    });
    FakeSocket.instances[0].fireOpen();
    FakeSocket.instances[0].fireClose();
    vi.runOnlyPendingTimers();
    expect(statuses).not.toContain("fallback");
    expect(FakeSocket.instances.length).toBe(2);
  });

  it("sends bye on an intentional close", () => {
    const socket = createDeviceSocket({ url: "ws://x", hello, WebSocketImpl: FakeSocket });
    const ws = FakeSocket.instances[0];
    ws.fireOpen();
    socket.close(true);
    expect(ws.sent.some((f) => f.type === "bye")).toBe(true);
    expect(ws.closed).toBe(true);
  });

  it("stands down, without reconnecting, when a newer socket replaced it", () => {
    const statuses = [];
    createDeviceSocket({
      url: "ws://x",
      hello,
      onStatus: (s) => statuses.push(s),
      WebSocketImpl: FakeSocket,
      setTimeoutImpl: (fn) => fn(),
    });
    FakeSocket.instances[0].fireOpen();
    FakeSocket.instances[0].fireClose(REPLACED_CLOSE_CODE);
    expect(FakeSocket.instances.length).toBe(1);
    expect(statuses[statuses.length - 1]).toBe("replaced");
  });

  it("backs off after repeated drops instead of reconnecting every second", () => {
    const delays = [];
    const timers = [];
    createDeviceSocket({
      url: "ws://x",
      hello,
      WebSocketImpl: FakeSocket,
      setTimeoutImpl: (fn, ms) => {
        delays.push(ms);
        timers.push(fn);
        return timers.length;
      },
    });
    // Opened once, then dropped three times in a row.
    FakeSocket.instances[0].fireOpen();
    FakeSocket.instances[0].fireClose();
    timers.shift()();
    FakeSocket.instances[1].fireClose();
    timers.shift()();
    FakeSocket.instances[2].fireClose();
    expect(delays).toEqual([RECONNECT_BACKOFF_MS[0], RECONNECT_BACKOFF_MS[1], RECONNECT_BACKOFF_MS[2]]);
  });

  it("tries the socket again after a spell of polling", () => {
    const delays = [];
    const timers = [];
    const statuses = [];
    createDeviceSocket({
      url: "ws://x",
      hello,
      onStatus: (s) => statuses.push(s),
      WebSocketImpl: FakeSocket,
      setTimeoutImpl: (fn, ms) => {
        delays.push(ms);
        timers.push(fn);
        return timers.length;
      },
    });
    FakeSocket.instances[0].fireClose();
    timers.shift()();
    FakeSocket.instances[1].fireClose();
    expect(statuses).toContain("fallback");
    expect(delays[delays.length - 1]).toBe(FALLBACK_RETRY_MS);
    // The retry opens a fresh socket; a server that now accepts it ends the polling.
    timers.shift()();
    expect(FakeSocket.instances.length).toBe(3);
    FakeSocket.instances[2].fireOpen();
    expect(statuses[statuses.length - 1]).toBe("open");
  });
});
