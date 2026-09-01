import { useEffect, useState } from "react";

import { getForYou } from "../../services/homeService";
import * as statsService from "../../services/statsService";

const EMPTY = {
  recentlyPlayed: [],
  forYou: [],
  topPlayed: [],
  topGenres: [],
};

/**
 * Everything the home page shows, fetched in parallel.
 *
 * Each rail resolves independently — the recommendation rail runs the full retrieval
 * pipeline and is much slower than the rest, so it must not hold up the page. A rail that
 * fails simply does not render; home should never become an error screen.
 */
export function useHomeData() {
  const [data, setData] = useState(EMPTY);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingForYou, setIsLoadingForYou] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const settle = (promise, key, transform = (value) => value) =>
      promise
        .then((value) => {
          if (!signal.aborted) {
            setData((previous) => ({ ...previous, [key]: transform(value) }));
          }
        })
        .catch(() => {});

    Promise.all([
      settle(statsService.getRecentlyPlayed(12, signal), "recentlyPlayed"),
      settle(statsService.getTopPlayed(12, signal), "topPlayed"),
      settle(
        statsService.getStatsOverview({ signal }),
        "topGenres",
        (overview) => overview.top_genres || [],
      ),
    ]).finally(() => {
      if (!signal.aborted) setIsLoading(false);
    });

    // Deliberately not awaited alongside the rest.
    getForYou({ limit: 12, signal })
      .then((tracks) => {
        if (!signal.aborted) setData((previous) => ({ ...previous, forYou: tracks }));
      })
      .catch(() => {})
      .finally(() => {
        if (!signal.aborted) setIsLoadingForYou(false);
      });

    return () => controller.abort();
  }, []);

  return { ...data, isLoading, isLoadingForYou };
}

/** "Good morning" / "Good afternoon" / "Good evening", by local clock. */
export function getGreeting(date = new Date()) {
  const hour = date.getHours();

  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}
