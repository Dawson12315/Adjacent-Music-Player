import { useCallback, useMemo, useRef, useState } from "react";

import { ScanContext } from "./ScanContext";
import { useLibrary } from "./LibraryContext";
import { useNotifications } from "./NotificationContext";
import { usePolling } from "../hooks/usePolling";
import * as settingsService from "../services/settingsService";

const SCAN_POLL_MS = 2500;

/** While the folder watcher is on, a slow poll keeps up with its imports: the
 * status line in Settings, the toast, the library refreshing itself. */
const WATCH_POLL_MS = 30000;

/** Library refreshes are throttled: counts growing every few seconds reads as
 * live without refetching seven endpoints on every poll. */
const LIBRARY_REFRESH_MIN_MS = 8000;

/**
 * App-level scan awareness.
 *
 * The scan itself runs in a background thread on the server; this provider
 * polls its progress while it runs, refreshes the library data as new tracks
 * land — so the sidebar counts and views grow during the scan — and announces
 * the result wherever the user happens to be, not just on the settings page
 * that started it.
 */
export function ScanProvider({ children }) {
  const { notify } = useNotifications();
  const { refreshLibrary } = useLibrary();

  const [progress, setProgress] = useState(null);
  const isScanning = Boolean(progress?.is_running);
  const watching = Boolean(progress?.watch?.enabled);

  const wasRunningRef = useRef(false);
  // The finished_at last seen; undefined until the first read, so a scan that
  // ended before login is not announced as news.
  const seenFinishedAtRef = useRef(undefined);
  const lastRefreshedAddedRef = useRef(0);
  const lastRefreshAtRef = useRef(0);

  const announce = useCallback(
    async (next) => {
      const added = next.added || 0;
      const plural = added === 1 ? "" : "s";
      // The watcher's imports are quieter: no toast for an import that found
      // nothing (a tag edit, a folder renamed), and the library only refreshes
      // when something landed.
      const fromWatch = String(next.source || "").startsWith("watch");

      if (next.last_result === "completed") {
        if (added > 0 || !fromWatch) await refreshLibrary();
        if (!fromWatch) {
          notify(`Library scan completed. Added ${added} new track${plural}.`);
        } else if (added > 0) {
          notify(`${added} new track${plural} picked up from the music folder.`);
        }
      } else if (next.error) {
        notify(next.error);
      }
    },
    [notify, refreshLibrary],
  );

  const fetchProgress = useCallback(async () => {
    try {
      const next = await settingsService.getScanProgress();
      setProgress(next);

      if (next.is_running) {
        wasRunningRef.current = true;

        const added = next.added || 0;
        const now = Date.now();

        if (
          added > lastRefreshedAddedRef.current &&
          now - lastRefreshAtRef.current >= LIBRARY_REFRESH_MIN_MS
        ) {
          lastRefreshedAddedRef.current = added;
          lastRefreshAtRef.current = now;
          await refreshLibrary();
        }
        return;
      }

      // Announce a scan exactly once: the one we watched run, or one that
      // started and finished between two polls — a watch import of a single
      // album is often that quick.
      const finishedAt = next.finished_at ?? null;
      const unseen =
        seenFinishedAtRef.current !== undefined &&
        finishedAt !== null &&
        finishedAt !== seenFinishedAtRef.current;
      const justEnded = wasRunningRef.current;

      wasRunningRef.current = false;
      seenFinishedAtRef.current = finishedAt;

      if (justEnded || unseen) {
        lastRefreshedAddedRef.current = 0;
        lastRefreshAtRef.current = 0;
        await announce(next);
      }
    } catch (error) {
      console.error("Failed to read scan progress", error);
    }
  }, [announce, refreshLibrary]);

  // Poll quickly while a scan runs — and while progress is still unknown,
  // which makes the first tick double as the on-login check for scans
  // already in flight — and slowly while the folder watcher is on.
  const pollQuickly = isScanning || progress === null;
  usePolling(fetchProgress, pollQuickly ? SCAN_POLL_MS : WATCH_POLL_MS, pollQuickly || watching);

  const startScan = useCallback(async () => {
    const result = await settingsService.scanLibrary();

    if (result.started) {
      wasRunningRef.current = true;
      lastRefreshedAddedRef.current = 0;
      lastRefreshAtRef.current = 0;
      setProgress((previous) => ({
        ...(previous || {}),
        is_running: true,
        files_seen: 0,
        added: 0,
        error: null,
      }));
      notify("Library scan started.");
    } else {
      notify("A scan is already running.");
    }

    fetchProgress();

    return result;
  }, [fetchProgress, notify]);

  const value = useMemo(
    () => ({
      progress,
      isScanning,
      startScan,
      // For the Settings page: read the state again right after a save.
      refreshProgress: fetchProgress,
    }),
    [progress, isScanning, startScan, fetchProgress],
  );

  return <ScanContext.Provider value={value}>{children}</ScanContext.Provider>;
}
