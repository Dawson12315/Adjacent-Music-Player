import { useEffect, useRef } from "react";

/**
 * Run a callback on an interval while `enabled` is true.
 *
 * Replaces two hand-rolled polling loops that each kept an interval id in a ref and
 * cleared it from four different places, including inside their own error handlers.
 * The interval is owned by the effect, so it cannot outlive the component.
 */
export function usePolling(callback, intervalMs, enabled) {
  const callbackRef = useRef(callback);

  // Synced in an effect rather than during render so the ref is only ever written after
  // commit; the interval effect below runs after this one and picks up the latest value.
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    let cancelled = false;

    const tick = () => {
      if (!cancelled) {
        callbackRef.current();
      }
    };

    tick();
    const intervalId = setInterval(tick, intervalMs);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [enabled, intervalMs]);
}
