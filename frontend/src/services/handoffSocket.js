/**
 * The handoff WebSocket: one connection to `/api/playback/ws`, reconnecting
 * with backoff and answering the server's pings. The browser's WebSocket sends
 * the session cookie on same-origin connections, so it authenticates the same
 * way every request does. This is the phone's deviceSocket verbatim — the
 * transport is identical — so the two clients stay in step.
 *
 * After two handshakes fail in a row it reports `fallback`, and the provider
 * switches to polling the HTTP twins — a proxy without WebSocket support, or a
 * network that drops the upgrade, still gets the one-device rule, only slower.
 *
 * The WebSocket class is injected so the whole thing runs against a fake in a
 * test; in the app it is the global one.
 */

export const RECONNECT_BACKOFF_MS = [1000, 2000, 5000, 10000];
/** Consecutive failed handshakes before we give up and tell the provider to poll. */
export const FALLBACK_AFTER_FAILURES = 2;

export function createDeviceSocket({
  url,
  hello,
  onFrame,
  onStatus,
  WebSocketImpl = typeof WebSocket !== "undefined" ? WebSocket : null,
  setTimeoutImpl = setTimeout,
  clearTimeoutImpl = clearTimeout,
}) {
  let socket = null;
  let closedByUs = false;
  let failures = 0;
  let everOpened = false;
  let reconnectTimer = null;
  let status = "idle";

  function report(next) {
    if (next !== status) {
      status = next;
      onStatus?.(next);
    }
  }

  function open() {
    if (!WebSocketImpl || !url) {
      report("fallback");
      return;
    }
    closedByUs = false;
    report(everOpened ? "connecting" : "connecting");
    try {
      socket = new WebSocketImpl(url);
    } catch {
      onFailure();
      return;
    }

    socket.onopen = () => {
      everOpened = true;
      failures = 0;
      report("open");
      try {
        socket.send(JSON.stringify(hello()));
      } catch {
        // The send can race a close; the reconnect will say hello again.
      }
    };

    socket.onmessage = (event) => {
      let frame;
      try {
        frame = JSON.parse(typeof event?.data === "string" ? event.data : "");
      } catch {
        return;
      }
      if (frame?.type === "ping") {
        try {
          socket.send(JSON.stringify({ type: "pong" }));
        } catch {
          // Lost the socket mid-pong; the reconnect handles it.
        }
        return;
      }
      onFrame?.(frame);
    };

    socket.onerror = () => {
      // onclose follows; the failure is counted there so it is counted once.
    };

    socket.onclose = () => {
      if (closedByUs) {
        report("closed");
        return;
      }
      onFailure();
    };
  }

  function onFailure() {
    socket = null;
    // A socket that had been open and dropped is a reconnect, not a handshake
    // failure: the server is there, the network blinked. Only never-opened
    // handshakes count toward giving up on WebSockets entirely.
    if (!everOpened) {
      failures += 1;
      if (failures >= FALLBACK_AFTER_FAILURES) {
        report("fallback");
        return;
      }
    }
    scheduleReconnect();
  }

  function scheduleReconnect() {
    report("connecting");
    const index = Math.min(failures, RECONNECT_BACKOFF_MS.length - 1);
    reconnectTimer = setTimeoutImpl(() => {
      reconnectTimer = null;
      open();
    }, RECONNECT_BACKOFF_MS[index]);
  }

  function send(frame) {
    if (socket && status === "open") {
      try {
        socket.send(JSON.stringify(frame));
        return true;
      } catch {
        return false;
      }
    }
    return false;
  }

  function close(sayBye = true) {
    closedByUs = true;
    if (reconnectTimer) {
      clearTimeoutImpl(reconnectTimer);
      reconnectTimer = null;
    }
    if (socket) {
      if (sayBye) {
        try {
          socket.send(JSON.stringify({ type: "bye" }));
        } catch {
          // Already gone.
        }
      }
      try {
        socket.close();
      } catch {
        // Already closed.
      }
      socket = null;
    }
    report("closed");
  }

  open();

  return {
    send,
    close,
    getStatus: () => status,
    /** For tests: whether a live socket is held. */
    _hasSocket: () => Boolean(socket),
  };
}
