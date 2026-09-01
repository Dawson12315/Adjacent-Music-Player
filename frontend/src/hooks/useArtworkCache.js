import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Lazy per-key artwork cache, shared by albums and artists.
 *
 * Replaces two near-identical effects that each depended on a freshly-sliced array and
 * on the cache they themselves wrote, so their bodies ran on every render. Here the
 * requested keys are compared against a ref, `ensure` is a stable callback, and a key is
 * recorded as in-flight before its request starts so concurrent callers cannot duplicate
 * a fetch.
 *
 * A key that resolves to no artwork is cached as an empty string, which is what stops it
 * from being retried forever.
 */
export function useArtworkCache(fetchArtwork) {
  const [map, setMap] = useState({});
  const requestedRef = useRef(new Set());
  const mountedRef = useRef(true);
  const fetchRef = useRef(fetchArtwork);

  useEffect(() => {
    fetchRef.current = fetchArtwork;
  }, [fetchArtwork]);

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
    };
  }, []);

  const ensure = useCallback(async (keys) => {
    const pending = [];

    keys.forEach((key) => {
      if (key && !requestedRef.current.has(key)) {
        requestedRef.current.add(key);
        pending.push(key);
      }
    });

    if (pending.length === 0) {
      return;
    }

    const entries = await Promise.all(
      pending.map(async (key) => {
        try {
          const data = await fetchRef.current(key);
          return [key, data?.artwork_path || ""];
        } catch {
          // Treat a failed lookup as "no artwork" rather than retrying on every render.
          return [key, ""];
        }
      }),
    );

    if (!mountedRef.current) {
      return;
    }

    setMap((previous) => ({ ...previous, ...Object.fromEntries(entries) }));
  }, []);

  /** Force a re-read after an upload, with a cache-busting suffix. */
  const set = useCallback((key, path) => {
    requestedRef.current.add(key);

    setMap((previous) => ({
      ...previous,
      [key]: path ? `${path}?v=${Date.now()}` : "",
    }));
  }, []);

  const reset = useCallback(() => {
    requestedRef.current = new Set();
    setMap({});
  }, []);

  return { map, ensure, set, reset };
}
