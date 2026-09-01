import { useCallback, useMemo, useRef, useState } from "react";

import { ScanContext } from "./ScanContext";
import { useLibrary } from "./LibraryContext";
import { useNotifications } from "./NotificationContext";
import { usePolling } from "../hooks/usePolling";
import * as settingsService from "../services/settingsService";

const SCAN_POLL_MS = 2500;

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

  const wasRunningRef = useRef(false);
  const lastRefreshedAddedRef = useRef(0);
  const lastRefreshAtRef = useRef(0);

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
      } else if (wasRunningRef.current) {
        // The scan we were watching just finished; announce it exactly once.
        wasRunningRef.current = false;
        lastRefreshedAddedRef.current = 0;
        lastRefreshAtRef.current = 0;

        if (next.last_result === "completed") {
          await refreshLibrary();
          notify(
            `Library scan completed. Added ${next.added} new track${
              next.added === 1 ? "" : "s"
            }.`,
          );
        } else if (next.error) {
          notify(next.error);
        }
      }
    } catch (error) {
      console.error("Failed to read scan progress", error);
    }
  }, [notify, refreshLibrary]);

  // Poll while a scan runs — and while progress is still unknown, which makes
  // the first tick double as the on-login check for scans already in flight.
  usePolling(fetchProgress, SCAN_POLL_MS, isScanning || progress === null);

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
    }),
    [progress, isScanning, startScan],
  );

  return <ScanContext.Provider value={value}>{children}</ScanContext.Provider>;
}
