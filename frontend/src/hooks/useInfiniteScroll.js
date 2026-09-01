import { useCallback, useEffect, useRef } from "react";

/**
 * Calls `onLoadMore` when a sentinel element scrolls into view.
 *
 * The observer is torn down and rebuilt whenever the callback or the enabled flag
 * changes, so it never fires against a stale closure, and `rootMargin` gives it a screen
 * of runway so the next page is already arriving by the time the user reaches the end.
 */
export function useInfiniteScroll({ onLoadMore, enabled = true, rootMargin = "600px" }) {
  const sentinelRef = useRef(null);
  const callbackRef = useRef(onLoadMore);

  useEffect(() => {
    callbackRef.current = onLoadMore;
  }, [onLoadMore]);

  const setSentinel = useCallback((node) => {
    sentinelRef.current = node;
  }, []);

  useEffect(() => {
    const node = sentinelRef.current;

    if (!node || !enabled || typeof IntersectionObserver === "undefined") {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          callbackRef.current?.();
        }
      },
      { rootMargin },
    );

    observer.observe(node);

    return () => observer.disconnect();
  }, [enabled, rootMargin]);

  return { sentinelRef, setSentinel };
}
