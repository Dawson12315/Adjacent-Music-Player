import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE_URL } from "../config";
import { describeDevice } from "../services/deviceIdentity";
import { createDeviceSocket } from "../services/handoffSocket";
import * as http from "../services/handoffHttp";
import { getHealth } from "../services/healthService";
import {
  claimFrame,
  commandFrame,
  handoffSocketUrl,
  helloFrame,
  readServerFrame,
  reportFrame,
  stateFrame,
  transferFrame,
} from "../services/handoffProtocol";

/** How often a polling browser asks for the lease and its waiting commands. */
const POLL_INTERVAL_MS = 15000;
/** The capability a server must advertise for any of this to turn on. */
export const HANDOFF_CAPABILITY = "device-handoff";

/**
 * The browser as one of the account's devices.
 *
 * Mounted inside the player so it can pause the audio, follow the holder, and
 * take a queue over. Inert until the server advertises the capability (asked
 * once after sign-in) and someone is signed in. Mirrors the phone's hook of
 * the same name, frame for frame.
 *
 * `deps`: currentUser, and the player bridges —
 *   getStateSnapshot() -> queue ids, index, position, flags, source
 *   pauseForRemote()   -> pause the audio; we are remote now
 *   takeOver(state)    -> load a handed-over queue and play/seek
 *   runCommand(action, args) -> perform a remote's request while holding
 */
export function useHandoff(deps) {
  const latest = useRef(deps);
  useEffect(() => {
    latest.current = deps;
  });

  const [capabilities, setCapabilities] = useState([]);
  const available = Boolean(deps.currentUser && capabilities.includes(HANDOFF_CAPABILITY));

  const [me, setMe] = useState(null);
  const [devices, setDevices] = useState([]);
  const [lease, setLease] = useState({ activeDeviceId: null, activeDeviceName: null, isActiveHere: false, stale: false });
  const [remote, setRemote] = useState(null);
  const [transport, setTransport] = useState("idle");

  const socketRef = useRef(null);
  const pollTimer = useRef(null);
  const versionRef = useRef(0);
  const isActiveHereRef = useRef(false);
  useEffect(() => {
    isActiveHereRef.current = lease.isActiveHere;
  }, [lease.isActiveHere]);

  // Learn the server's capabilities once signed in.
  useEffect(() => {
    if (!deps.currentUser) {
      setCapabilities([]);
      return undefined;
    }
    let cancelled = false;
    getHealth()
      .then((health) => {
        if (!cancelled) setCapabilities(health.capabilities);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [deps.currentUser]);

  // This browser's identity, resolved synchronously once available.
  useEffect(() => {
    if (available) setMe(describeDevice());
    else setMe(null);
  }, [available]);

  const applyLease = useCallback((reading) => {
    setLease({
      activeDeviceId: reading.activeDeviceId,
      activeDeviceName: reading.activeDeviceName ?? null,
      isActiveHere: reading.isActiveHere,
      stale: Boolean(reading.stale),
    });
    if (reading.state?.version != null) versionRef.current = Math.max(versionRef.current, reading.state.version);

    if (reading.isActiveHere) {
      setRemote(null);
      return;
    }
    latest.current.pauseForRemote?.();
    if (reading.state) {
      setRemote({
        trackId: reading.state.current_track_id ?? null,
        position: Number(reading.state.current_time_seconds) || 0,
        playing: Boolean(reading.state.is_playing),
        shuffle: Boolean(reading.state.is_shuffle),
        loop: Boolean(reading.state.is_loop),
        reportedAtMs: Date.now(),
      });
    }
  }, []);

  const onFrame = useCallback(
    (frame) => {
      const reading = readServerFrame(frame, me?.deviceId);
      if (!reading) return;
      switch (reading.kind) {
        case "devices":
          setDevices(reading.devices);
          if (reading.lease) {
            applyLease({
              activeDeviceId: reading.lease.active_device_id ?? null,
              activeDeviceName: reading.lease.active_device_name ?? null,
              isActiveHere: reading.lease.active_device_id === me?.deviceId,
              stale: Boolean(reading.lease.stale),
              state: reading.lease.state,
            });
          }
          break;
        case "lease":
          applyLease(reading);
          break;
        case "state":
          if (!isActiveHereRef.current && reading.state) {
            setRemote((prev) => ({
              ...(prev || {}),
              trackId: reading.state.current_track_id ?? prev?.trackId ?? null,
              position: Number(reading.state.current_time_seconds) || 0,
              playing: Boolean(reading.state.is_playing),
              reportedAtMs: Date.now(),
            }));
          }
          break;
        case "take_over":
          latest.current.takeOver?.(reading.state);
          break;
        case "command":
          if (isActiveHereRef.current) latest.current.runCommand?.(reading.action, reading.args);
          break;
        default:
          break;
      }
    },
    [applyLease, me?.deviceId],
  );

  const onFrameRef = useRef(onFrame);
  useEffect(() => {
    onFrameRef.current = onFrame;
  }, [onFrame]);

  const startPolling = useCallback(() => {
    if (pollTimer.current || !me) return;
    const tick = async () => {
      try {
        const data = await http.getDevices(me.deviceId);
        if (Array.isArray(data?.devices)) setDevices(data.devices);
        if (data?.lease) {
          applyLease({
            activeDeviceId: data.lease.active_device_id ?? null,
            activeDeviceName: data.lease.active_device_name ?? null,
            isActiveHere: data.lease.active_device_id === me.deviceId,
            stale: Boolean(data.lease.stale),
            state: data.lease.state,
          });
        }
        (data?.pending_commands || []).forEach((cmd) => {
          if (isActiveHereRef.current) latest.current.runCommand?.(cmd.action, cmd.args);
        });
      } catch {
        // A failed poll is a blip; the next tries again.
      }
    };
    tick();
    pollTimer.current = setInterval(tick, POLL_INTERVAL_MS);
  }, [applyLease, me]);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  // Open the socket (and fall back to polling) while signed in.
  useEffect(() => {
    if (!available || !me) {
      socketRef.current?.close(false);
      socketRef.current = null;
      stopPolling();
      setTransport("idle");
      return undefined;
    }

    const socket = createDeviceSocket({
      url: handoffSocketUrl(API_BASE_URL),
      hello: () => helloFrame(me),
      onFrame: (frame) => onFrameRef.current(frame),
      onStatus: (status) => {
        setTransport(status);
        if (status === "fallback") {
          http.sayHello(me).catch(() => {});
          startPolling();
        } else if (status === "open") {
          stopPolling();
        }
      },
    });
    socketRef.current = socket;

    return () => {
      socket.close(true);
      socketRef.current = null;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- me identity + availability are the real deps
  }, [available, me?.deviceId]);

  // --- actions ---------------------------------------------------------------

  const nextVersion = useCallback(() => {
    versionRef.current += 1;
    return versionRef.current;
  }, []);

  const sendOrPost = useCallback((frame, httpCall) => {
    const sent = socketRef.current?.send(frame);
    if (!sent) httpCall().catch(() => {});
  }, []);

  const claim = useCallback(() => {
    if (!available || !me) return;
    const snap = latest.current.getStateSnapshot?.();
    if (!snap) return;
    const state = stateFrame({ ...snap, version: nextVersion() });
    isActiveHereRef.current = true;
    setLease((prev) => ({ ...prev, activeDeviceId: me.deviceId, activeDeviceName: me.name, isActiveHere: true, stale: false }));
    setRemote(null);
    sendOrPost(claimFrame(state), () => http.claim(me.deviceId, state));
  }, [available, me, nextVersion, sendOrPost]);

  const reportPosition = useCallback(() => {
    if (!available || !me || !isActiveHereRef.current) return;
    const snap = latest.current.getStateSnapshot?.();
    if (!snap) return;
    const frame = reportFrame({ ...snap, version: nextVersion() });
    const { type: _type, ...position } = frame;
    sendOrPost(frame, () => http.report(me.deviceId, position));
  }, [available, me, nextVersion, sendOrPost]);

  const transferTo = useCallback(
    (toDeviceId) => {
      if (!available || !me) return;
      const snap = isActiveHereRef.current ? latest.current.getStateSnapshot?.() : null;
      const state = snap ? stateFrame({ ...snap, version: nextVersion() }) : null;
      sendOrPost(transferFrame(toDeviceId, state), () => http.transfer(me.deviceId, toDeviceId, state));
    },
    [available, me, nextVersion, sendOrPost],
  );

  const sendCommand = useCallback(
    (action, args = {}) => {
      if (!available || !me) return;
      sendOrPost(commandFrame(action, args), () => http.command(me.deviceId, action, args));
    },
    [available, me, sendOrPost],
  );

  return {
    available,
    me,
    devices,
    activeDeviceId: lease.activeDeviceId,
    activeName: lease.activeDeviceName,
    isActiveHere: lease.isActiveHere,
    stale: lease.stale,
    remote,
    transport,
    claim,
    reportPosition,
    transferTo,
    sendCommand,
  };
}

export default useHandoff;
