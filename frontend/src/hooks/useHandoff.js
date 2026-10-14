import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
/** How long the player waits for the first lease reading before loading a stream anyway. */
export const LEASE_WAIT_MS = 4000;

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
 *   onError({code, message}) -> the server refused something we asked for
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
  // Whether the first lease reading has arrived. Until then the player must
  // not ask for a stream, which the server refuses to a non-holder while
  // another device plays. Never held for long: a socket that cannot connect
  // and a server that never answers both release it after a few seconds.
  const [firstReading, setFirstReading] = useState(false);
  const [waitedOut, setWaitedOut] = useState(false);
  useEffect(() => {
    if (!available) return undefined;
    const timer = setTimeout(() => setWaitedOut(true), LEASE_WAIT_MS);
    return () => clearTimeout(timer);
  }, [available]);
  const leaseKnown = !available || firstReading || waitedOut;

  const socketRef = useRef(null);
  const pollTimer = useRef(null);
  const versionRef = useRef(0);
  const isActiveHereRef = useRef(false);
  useEffect(() => {
    isActiveHereRef.current = lease.isActiveHere;
  }, [lease.isActiveHere]);
  // Who held the lease at the last reading, for the claim path to decide
  // whether it is taking the music from someone.
  const holderRef = useRef(null);
  // When this browser last claimed. A lease reading older than the claim —
  // a poll already in flight, a frame from before the claim landed — must
  // not pause what the claim just started.
  const claimedAtRef = useRef(0);
  const claimVersionRef = useRef(0);
  const CLAIM_SETTLE_MS = 3000;

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
    const activeDeviceId = reading.activeDeviceId ?? null;
    const stale = Boolean(reading.stale);
    if (reading.state?.version != null) versionRef.current = Math.max(versionRef.current, reading.state.version);

    // A reading that says someone else holds it but predates our own claim
    // was true before the claim. Our claim is the newer fact; keep it. Age is
    // judged by version where the reading carries one — so another device's
    // *later* claim is still obeyed — and by time otherwise.
    if (isActiveHereRef.current && !reading.isActiveHere) {
      const readingVersion = reading.state?.version;
      const older =
        readingVersion != null
          ? Number(readingVersion) < claimVersionRef.current
          : Date.now() - claimedAtRef.current < CLAIM_SETTLE_MS;
      if (older) return;
    }

    holderRef.current = activeDeviceId;
    setFirstReading(true);
    setLease({
      activeDeviceId,
      activeDeviceName: reading.activeDeviceName ?? null,
      isActiveHere: reading.isActiveHere,
      stale,
    });

    if (reading.isActiveHere) {
      setRemote(null);
      return;
    }
    // Nobody holds the lease, or the holder has gone quiet: nothing to follow
    // and no one to make room for. This browser keeps doing what it was
    // doing. Pausing here is what stopped the music every time the server
    // said "nobody" after a reconnect.
    if (!activeDeviceId || stale) {
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
          setFirstReading(true);
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
          if (reading.state?.version != null) versionRef.current = Math.max(versionRef.current, reading.state.version);
          if (!isActiveHereRef.current && reading.state) {
            setRemote((prev) => ({
              ...(prev || {}),
              trackId: reading.state.current_track_id ?? prev?.trackId ?? null,
              position: Number(reading.state.current_time_seconds) || 0,
              playing: Boolean(reading.state.is_playing),
              // A tick carries the flags too, so a shuffle or repeat toggled
              // on the holder shows here without waiting for a lease frame.
              shuffle: reading.state.is_shuffle != null ? Boolean(reading.state.is_shuffle) : prev?.shuffle,
              loop: reading.state.is_loop != null ? Boolean(reading.state.is_loop) : prev?.loop,
              reportedAtMs: Date.now(),
            }));
          }
          break;
        case "take_over":
          // The server moved the lease to us before sending this. Mark it so
          // the reports go out as the holder's; the lease frame that follows
          // (newer servers send us one too) agrees.
          if (me) {
            isActiveHereRef.current = true;
            holderRef.current = me.deviceId;
            claimedAtRef.current = Date.now();
            setLease({ activeDeviceId: me.deviceId, activeDeviceName: me.name, isActiveHere: true, stale: false });
            setRemote(null);
          }
          latest.current.takeOver?.(reading.state);
          break;
        case "command":
          if (isActiveHereRef.current) latest.current.runCommand?.(reading.action, reading.args);
          break;
        case "error":
          latest.current.onError?.({ code: reading.code, message: reading.message });
          break;
        default:
          break;
      }
    },
    [applyLease, me],
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
        // No socket, for either reason — a proxy that drops the upgrade, or
        // a second tab of this browser that took the socket over — means
        // polling, or this tab hears nothing and can play over the others.
        if (status === "fallback" || status === "replaced") {
          Promise.resolve(http.sayHello(me)).catch(() => {});
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
    if (!sent) {
      httpCall().catch((error) => {
        // The HTTP twin's refusal is the same news the socket would have
        // framed as an error; a network failure is not worth a line.
        if (error?.status >= 400) {
          latest.current.onError?.({
            code: error?.detail?.code || "request_failed",
            message: error?.detail?.message || error?.message || "The server could not do that.",
          });
        }
      });
    }
  }, []);

  /**
   * This browser is playing now — called from the intent to play, before the
   * audio element asks for the stream. Resolves at once when this browser
   * already holds the lease or nobody does; when another device is playing
   * it waits for the HTTP claim to land, so the stream gate sees the lease
   * moved. `overrides` patch the snapshot for what is about to be true.
   */
  const claim = useCallback(
    async (overrides = {}) => {
      if (!available || !me) return;
      const snap = latest.current.getStateSnapshot?.();
      if (!snap) return;
      const takingOver = !isActiveHereRef.current && holderRef.current && holderRef.current !== me.deviceId;
      const version = nextVersion();
      const state = stateFrame({ ...snap, ...overrides, version });
      isActiveHereRef.current = true;
      holderRef.current = me.deviceId;
      claimedAtRef.current = Date.now();
      claimVersionRef.current = version;
      setLease((prev) => ({ ...prev, activeDeviceId: me.deviceId, activeDeviceName: me.name, isActiveHere: true, stale: false }));
      setRemote(null);
      if (takingOver) {
        try {
          await http.claim(me.deviceId, state);
        } catch {
          socketRef.current?.send(claimFrame(state));
        }
        return;
      }
      sendOrPost(claimFrame(state), () => http.claim(me.deviceId, state));
    },
    [available, me, nextVersion, sendOrPost],
  );

  /** The holder's report: on a timer while playing, and at once on a change. */
  const reportPosition = useCallback(
    (overrides = {}) => {
      if (!available || !me || !isActiveHereRef.current) return;
      const snap = latest.current.getStateSnapshot?.();
      if (!snap) return;
      const frame = reportFrame({ ...snap, ...overrides, version: nextVersion() });
      const { type: _type, ...position } = frame;
      sendOrPost(frame, () => http.report(me.deviceId, position));
    },
    [available, me, nextVersion, sendOrPost],
  );

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

  // One object per change, so the provider's value and the player bar do not
  // re-render on every render of the hook's host.
  return useMemo(
    () => ({
      available,
      me,
      devices,
      activeDeviceId: lease.activeDeviceId,
      activeName: lease.activeDeviceName,
      isActiveHere: lease.isActiveHere,
      stale: lease.stale,
      leaseKnown,
      remote,
      transport,
      claim,
      reportPosition,
      transferTo,
      sendCommand,
    }),
    [available, me, devices, lease, leaseKnown, remote, transport, claim, reportPosition, transferTo, sendCommand],
  );
}

export default useHandoff;
