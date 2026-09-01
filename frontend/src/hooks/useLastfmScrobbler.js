import { useEffect, useRef } from "react";

import { scrobble, updateNowPlaying } from "../services/tracksService";

const SCROBBLE_AFTER_SECONDS = 40;

/**
 * Reports now-playing immediately and scrobbles once a track has actually been listened
 * to for long enough.
 *
 * Listened time is accumulated from a timer rather than read off the audio element's
 * position, so seeking forward does not count as listening. Ticks longer than five
 * seconds are discarded, which is how a backgrounded tab avoids banking time it never
 * played.
 *
 * Last.fm may not be configured at all; failures are expected and stay silent.
 */
export function useLastfmScrobbler({ track, isPlaying, enabled }) {
  const listenedSecondsRef = useRef(0);
  const lastTickRef = useRef(null);
  const nowPlayingSentForRef = useRef(null);
  const scrobbledForRef = useRef(null);

  const trackId = track?.id ?? null;

  useEffect(() => {
    listenedSecondsRef.current = 0;
    lastTickRef.current = null;
    nowPlayingSentForRef.current = null;
    scrobbledForRef.current = null;
  }, [trackId]);

  useEffect(() => {
    if (!enabled || !trackId || !isPlaying) {
      lastTickRef.current = null;
      return undefined;
    }

    const intervalId = setInterval(() => {
      const now = Date.now();

      if (lastTickRef.current == null) {
        lastTickRef.current = now;
        return;
      }

      const elapsedSeconds = (now - lastTickRef.current) / 1000;
      lastTickRef.current = now;

      if (elapsedSeconds > 0 && elapsedSeconds < 5) {
        listenedSecondsRef.current += elapsedSeconds;
      }

      if (
        listenedSecondsRef.current >= SCROBBLE_AFTER_SECONDS &&
        scrobbledForRef.current !== trackId
      ) {
        scrobbledForRef.current = trackId;
        scrobble(trackId).catch(() => {});
      }
    }, 1000);

    return () => clearInterval(intervalId);
  }, [enabled, trackId, isPlaying]);

  useEffect(() => {
    if (!enabled || !trackId || !isPlaying) {
      return;
    }

    if (nowPlayingSentForRef.current === trackId) {
      return;
    }

    nowPlayingSentForRef.current = trackId;
    updateNowPlaying(trackId).catch(() => {});
  }, [enabled, trackId, isPlaying]);
}
