/**
 * The frames the browser and the server exchange over the handoff socket, and
 * the reading of what comes back. The same protocol the phone speaks, kept as
 * its own module so the shape is tested apart from the socket.
 *
 * Client → server: hello, claim, state, transfer, command, bye.
 * Server → client: devices, lease, state, take_over, command, ping.
 */

export const COMMANDS = ["play", "pause", "next", "previous", "seek", "shuffle", "repeat", "volume"];

export function helloFrame(device) {
  return {
    type: "hello",
    device_id: device.deviceId,
    name: device.name,
    kind: device.kind,
    platform: device.platform,
    app_version: device.appVersion,
  };
}

export function stateFrame({ trackId, queue, index, position, playing, shuffle, loop, source, version }) {
  const ids = (queue || []).slice(0, 5000).map((value) => Number(value)).filter((value) => Number.isFinite(value));
  const safeIndex = Number.isFinite(index) ? Math.max(-1, Math.min(index, ids.length - 1)) : -1;
  return {
    current_track_id: trackId == null ? null : Number(trackId),
    queue_index: safeIndex,
    current_time_seconds: Math.max(0, Math.round(Number(position) || 0)),
    is_playing: Boolean(playing),
    is_shuffle: Boolean(shuffle),
    is_loop: Boolean(loop),
    queue_track_ids: ids,
    source_type: source?.source_type ?? null,
    source_id: source?.source_id ?? null,
    ...(version == null ? {} : { version: Number(version) }),
  };
}

export function claimFrame(state) {
  return { type: "claim", state };
}

export function reportFrame({ trackId, index, position, playing, shuffle, loop, version }) {
  return {
    type: "state",
    current_track_id: trackId == null ? null : Number(trackId),
    queue_index: Number.isFinite(index) ? index : null,
    current_time_seconds: Math.max(0, Math.round(Number(position) || 0)),
    is_playing: Boolean(playing),
    is_shuffle: Boolean(shuffle),
    is_loop: Boolean(loop),
    ...(version == null ? {} : { version: Number(version) }),
  };
}

export function transferFrame(toDeviceId, state) {
  return { type: "transfer", to: toDeviceId, ...(state ? { state } : {}) };
}

export function commandFrame(action, args = {}) {
  if (!COMMANDS.includes(action)) throw new Error(`unknown handoff command: ${action}`);
  return { type: "command", action, args };
}

export const byeFrame = { type: "bye" };

export function readServerFrame(frame, myDeviceId) {
  if (!frame || typeof frame !== "object") return null;
  switch (frame.type) {
    case "devices":
      return {
        kind: "devices",
        devices: Array.isArray(frame.devices) ? frame.devices : [],
        lease: frame.lease || null,
        activeDeviceId: frame.lease?.active_device_id ?? null,
        isActiveHere: frame.lease?.active_device_id === myDeviceId,
      };
    case "lease":
      return {
        kind: "lease",
        activeDeviceId: frame.active_device_id ?? null,
        activeDeviceName: frame.active_device_name ?? null,
        stale: Boolean(frame.stale),
        isActiveHere: frame.active_device_id === myDeviceId,
        state: frame.state || null,
      };
    case "state":
      return { kind: "state", state: frame };
    case "take_over":
      return { kind: "take_over", state: frame.state || null };
    case "command":
      return { kind: "command", action: frame.action, args: frame.args || {} };
    default:
      return null;
  }
}

/** The remote's elapsed position now, interpolated from its last report. */
export function interpolatedPosition(remote, nowMs = Date.now()) {
  if (!remote) return 0;
  const base = Number(remote.position) || 0;
  if (!remote.playing || !remote.reportedAtMs) return base;
  return base + Math.max(0, (nowMs - remote.reportedAtMs) / 1000);
}

/** The API base's WebSocket URL for the handoff endpoint. */
export function handoffSocketUrl(apiBaseUrl) {
  // apiBaseUrl may be "" (same origin) or an absolute URL.
  try {
    const base = apiBaseUrl || (typeof window !== "undefined" ? window.location.origin : "");
    const url = new URL(base, typeof window !== "undefined" ? window.location.href : undefined);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = url.pathname.replace(/\/+$/, "") + "/api/playback/ws";
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return null;
  }
}
