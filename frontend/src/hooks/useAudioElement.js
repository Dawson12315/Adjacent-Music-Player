import { useCallback, useEffect, useRef, useState } from "react";

import { streamUrl } from "../services/tracksService";

const ERROR_MESSAGES = {
  1: "Playback was aborted.",
  2: "A network error interrupted playback.",
  3: "This file could not be decoded.",
  4: "This audio format is not supported, or the file is missing.",
};

const EMPTY_PROGRESS = { trackId: null, currentTime: 0, duration: 0 };

/**
 * Owns the single <audio> element and everything imperative about it.
 *
 * Three defects the previous inline version had are addressed here:
 *
 *   - Changing `src` while a play() promise is pending rejects it with AbortError, which
 *     the old catch-all treated as a real failure and used to force the player into a
 *     paused state, so skipping quickly through tracks stopped playback. Play attempts
 *     are generation-tagged now and stale rejections are ignored.
 *   - A pending seek restored from the server session was applied to whatever track
 *     happened to load next, so switching tracks mid-restore jumped the new track to the
 *     old position. Seeks carry the track they belong to.
 *   - There was no error handler at all, so a missing file or an unsupported codec
 *     produced silence with the UI still showing the track as playing.
 *
 * Progress is stored together with the track it belongs to, so a track change resets the
 * reported position by derivation rather than by setting state from an effect.
 */
export function useAudioElement({ track, isPlaying, volume, isMuted, onPlaybackError }) {
  const audioRef = useRef(null);
  const [progress, setProgress] = useState(EMPTY_PROGRESS);

  const pendingSeekRef = useRef(null);
  const playGenerationRef = useRef(0);
  const errorHandlerRef = useRef(onPlaybackError);

  const trackId = track?.id ?? null;

  useEffect(() => {
    errorHandlerRef.current = onPlaybackError;
  }, [onPlaybackError]);

  // Values only count for the track they were measured on.
  const isCurrent = progress.trackId === trackId;
  const currentTime = isCurrent ? progress.currentTime : 0;
  const duration = isCurrent ? progress.duration : 0;

  /** Queue a seek to apply once the given track's metadata has loaded. */
  const requestSeek = useCallback((seconds, forTrackId) => {
    pendingSeekRef.current = { trackId: forTrackId, time: seconds };
  }, []);

  const seek = useCallback(
    (seconds) => {
      const audio = audioRef.current;

      if (!audio || !Number.isFinite(seconds)) {
        return;
      }

      audio.currentTime = seconds;
      setProgress((previous) => ({ ...previous, trackId, currentTime: seconds }));
    },
    [trackId],
  );

  // Point the element at the selected track.
  useEffect(() => {
    const audio = audioRef.current;

    if (!audio || !trackId) {
      return;
    }

    playGenerationRef.current += 1;
    audio.src = streamUrl(trackId);
    audio.load();
  }, [trackId]);

  // Mirror the desired play state onto the element.
  useEffect(() => {
    const audio = audioRef.current;

    if (!audio || !trackId) {
      return;
    }

    if (!isPlaying) {
      audio.pause();
      return;
    }

    const generation = playGenerationRef.current;
    const result = audio.play();

    if (result && typeof result.catch === "function") {
      result.catch((error) => {
        // A track change superseded this attempt; the new one owns the state now.
        if (error.name === "AbortError" || generation !== playGenerationRef.current) {
          return;
        }

        // Autoplay policy blocks playback no gesture asked for — expected when a session
        // is restored on load, and not something to report to the user.
        errorHandlerRef.current?.({
          kind: error.name === "NotAllowedError" ? "autoplay-blocked" : "play-failed",
          message: "Could not start playback.",
        });
      });
    }
  }, [isPlaying, trackId]);

  useEffect(() => {
    const audio = audioRef.current;

    if (!audio) {
      return;
    }

    audio.volume = volume;
    audio.muted = isMuted;
  }, [volume, isMuted]);

  const handleTimeUpdate = useCallback(() => {
    const audio = audioRef.current;

    if (!audio) {
      return;
    }

    setProgress((previous) => ({
      trackId,
      currentTime: audio.currentTime,
      duration: previous.trackId === trackId ? previous.duration : audio.duration || 0,
    }));
  }, [trackId]);

  const handleLoadedMetadata = useCallback(() => {
    const audio = audioRef.current;

    if (!audio) {
      return;
    }

    const pending = pendingSeekRef.current;
    let startAt = 0;

    if (pending && Number.isFinite(pending.time) && pending.trackId === trackId) {
      audio.currentTime = pending.time;
      startAt = pending.time;
    }

    // Drop the request either way: it belonged to a track that is no longer loading.
    pendingSeekRef.current = null;

    setProgress({ trackId, currentTime: startAt, duration: audio.duration || 0 });
  }, [trackId]);

  const handleError = useCallback(() => {
    const code = audioRef.current?.error?.code;

    errorHandlerRef.current?.({
      kind: "media-error",
      message: ERROR_MESSAGES[code] || "This track could not be played.",
    });
  }, []);

  return {
    audioRef,
    currentTime,
    duration,
    seek,
    requestSeek,
    handleTimeUpdate,
    handleLoadedMetadata,
    handleError,
  };
}
