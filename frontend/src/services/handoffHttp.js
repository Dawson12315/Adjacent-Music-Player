/**
 * The HTTP twins of the handoff socket, for when the socket cannot be held: a
 * proxy that will not carry a WebSocket, a blocked upgrade. Every call carries
 * the device id in the header the server reads. Polling `getDevices` also
 * returns any commands that were waiting while this browser had no socket.
 */

import { apiClient } from "./apiClient";

const DEVICE_HEADER = "X-Adjacent-Device";

function withDevice(deviceId) {
  return { headers: { [DEVICE_HEADER]: deviceId } };
}

export function sayHello(device) {
  return apiClient.post("/api/playback/devices/hello", {
    device_id: device.deviceId,
    name: device.name,
    kind: device.kind,
    platform: device.platform,
    app_version: device.appVersion,
  });
}

export function getDevices(deviceId) {
  return apiClient.get("/api/playback/devices", withDevice(deviceId));
}

export function claim(deviceId, state) {
  return apiClient.post("/api/playback/claim", { state }, withDevice(deviceId));
}

export function report(deviceId, position) {
  return apiClient.post("/api/playback/state", position, withDevice(deviceId));
}

export function transfer(deviceId, toDeviceId, state) {
  return apiClient.post("/api/playback/transfer", { to: toDeviceId, ...(state ? { state } : {}) }, withDevice(deviceId));
}

export function command(deviceId, action, args = {}) {
  return apiClient.post("/api/playback/command", { action, args }, withDevice(deviceId));
}
