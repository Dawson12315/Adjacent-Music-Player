import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createDeviceSocket, FALLBACK_AFTER_FAILURES } from "./handoffSocket";

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
  fireClose() {
    this.onclose?.();
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
});
