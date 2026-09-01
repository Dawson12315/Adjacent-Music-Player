import { useCallback, useEffect, useState } from "react";

import * as statsService from "../../services/statsService";

const EMPTY = {
  summary: null,
  playsOverTime: [],
  topArtists: [],
  topAlbums: [],
  topGenres: [],
  bySource: [],
  byHour: [],
  topPlayed: [],
  mostLiked: [],
  mostSkipped: [],
};

/**
 * Loads the whole insights page in one pass.
 *
 * Every panel resolves independently so a single failing aggregate does not blank the
 * page. The `-detailed` track endpoints carry the play/like/skip counters, which is what
 * makes the ranked lists meaningful — the original endpoints ordered by those counters
 * and then discarded them.
 */
export function useInsightsData() {
  const [data, setData] = useState(EMPTY);
  const [isLoading, setIsLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    setIsLoading(true);

    const settle = (promise, key, transform = (value) => value) =>
      promise
        .then((value) => {
          if (!signal.aborted) {
            setData((previous) => ({ ...previous, [key]: transform(value) }));
          }
        })
        .catch(() => {});

    Promise.all([
      settle(statsService.getSummary({ signal }), "summary"),
      settle(statsService.getPlaysOverTime({ days: 30, signal }), "playsOverTime"),
      settle(statsService.getTopArtists({ limit: 8, signal }), "topArtists"),
      settle(statsService.getTopAlbums({ limit: 8, signal }), "topAlbums"),
      settle(statsService.getBySource({ signal }), "bySource"),
      settle(statsService.getByHour({ signal }), "byHour"),
      settle(statsService.getTopPlayed(8, signal), "topPlayed"),
      settle(statsService.getMostLiked(8, signal), "mostLiked"),
      settle(statsService.getMostSkipped(8, signal), "mostSkipped"),
      settle(
        statsService.getStatsOverview({ signal }),
        "topGenres",
        (overview) => overview.top_genres || [],
      ),
    ]).finally(() => {
      if (!signal.aborted) setIsLoading(false);
    });

    return () => controller.abort();
  }, [reloadKey]);

  return { ...data, isLoading, refresh };
}

/** Seconds to a human span. Listening time is an estimate; the caller says so. */
export function formatListeningTime(seconds) {
  if (!seconds || seconds < 60) {
    return { value: Math.round(seconds || 0), unit: "sec" };
  }

  const minutes = seconds / 60;

  if (minutes < 90) {
    return { value: Math.round(minutes), unit: "min" };
  }

  return { value: (minutes / 60).toFixed(1), unit: "hrs" };
}

export function formatPercent(ratio) {
  return `${Math.round((ratio || 0) * 100)}%`;
}
