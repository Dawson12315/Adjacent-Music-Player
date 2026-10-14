import { useCallback, useEffect, useRef } from "react";

import { savePlaybackState } from "../services/playbackService";

const DEBOUNCE_MS = 800;
const PROGRESS_INTERVAL_MS = 10000;

/**
 * Keeps the server-side playback session in step so playback resumes after a reload.
 *
 * This replaces two effects that both wrote the session with overlapping dependency
 * arrays — a pause produced two identical requests — and neither of which was throttled,
 * so every queue mutation and flag toggle was its own write. Each PUT deletes and
 * re-inserts the entire queue server-side, so that mattered.
 *
 * Structural changes are debounced; progress is written on a slow interval while playing
 * and flushed on pause, on unmount, and when the page is hidden.
 */
export function usePlaybackPersistence({ enabled, snapshot, getCurrentTime, deviceId = null }) {
  const snapshotRef = useRef(snapshot);
  const getCurrentTimeRef = useRef(getCurrentTime);
  const deviceIdRef = useRef(deviceId);
  const timeoutRef = useRef(null);

  useEffect(() => {
    snapshotRef.current = snapshot;
    getCurrentTimeRef.current = getCurrentTime;
    deviceIdRef.current = deviceId;
  }, [snapshot, getCurrentTime, deviceId]);

  const save = useCallback(async () => {
    try {
      const position = getCurrentTimeRef.current();
      // A null position means "not yet known" (a restored seek still
      // pending): the write would only replace a real position with zero.
      if (position == null) return;
      await savePlaybackState({
        ...snapshotRef.current,
        currentTimeSeconds: position,
        deviceId: deviceIdRef.current,
      });
    } catch (error) {
      // A 409 is the server keeping the playing device's state over this
      // one's, which is the rule working; anything else is worth a line.
      if (error?.status !== 409) console.error("Failed to save playback state", error);
    }
  }, []);

  const scheduleSave = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      timeoutRef.current = null;
      save();
    }, DEBOUNCE_MS);
  }, [save]);

  const {
    currentTrackId,
    queueIndex,
    isPlaying,
    isShuffle,
    isLoop,
    queueTrackIds,
  } = snapshot;

  // A stable identity for the queue's contents, so a re-created array does not by itself
  // trigger a write.
  const queueSignature = queueTrackIds.join(",");

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    scheduleSave();

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [
    enabled,
    scheduleSave,
    currentTrackId,
    queueIndex,
    isPlaying,
    isShuffle,
    isLoop,
    queueSignature,
  ]);

  // Periodic progress checkpoints while playing.
  useEffect(() => {
    if (!enabled || !isPlaying) {
      return undefined;
    }

    const intervalId = setInterval(save, PROGRESS_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [enabled, isPlaying, save]);

  // Best-effort flush when the tab goes away or the player unmounts.
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    const handleHide = () => {
      if (document.visibilityState === "hidden") {
        save();
      }
    };

    window.addEventListener("pagehide", save);
    document.addEventListener("visibilitychange", handleHide);

    return () => {
      window.removeEventListener("pagehide", save);
      document.removeEventListener("visibilitychange", handleHide);
      save();
    };
  }, [enabled, save]);
}
