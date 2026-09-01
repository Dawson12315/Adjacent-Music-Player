import { useEffect, useRef } from "react";

/**
 * Wires OS-level media controls (hardware keys, lock screen, notification shade).
 *
 * Handlers are held in a ref so the effect registers once rather than tearing down and
 * re-registering every time the queue or a flag changes.
 */
export function useMediaSession({ track, isPlaying, onPlay, onPause, onNext, onPrevious }) {
  const handlersRef = useRef({ onPlay, onPause, onNext, onPrevious });

  useEffect(() => {
    handlersRef.current = { onPlay, onPause, onNext, onPrevious };
  }, [onPlay, onPause, onNext, onPrevious]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) {
      return undefined;
    }

    const actions = {
      play: () => handlersRef.current.onPlay?.(),
      pause: () => handlersRef.current.onPause?.(),
      previoustrack: () => handlersRef.current.onPrevious?.(),
      nexttrack: () => handlersRef.current.onNext?.(),
    };

    Object.entries(actions).forEach(([action, handler]) => {
      try {
        navigator.mediaSession.setActionHandler(action, handler);
      } catch {
        // Not every browser supports every action.
      }
    });

    return () => {
      Object.keys(actions).forEach((action) => {
        try {
          navigator.mediaSession.setActionHandler(action, null);
        } catch {
          // Ignore.
        }
      });
    };
  }, []);

  useEffect(() => {
    if (!("mediaSession" in navigator)) {
      return;
    }

    if (!track) {
      navigator.mediaSession.metadata = null;
      return;
    }

    navigator.mediaSession.metadata = new MediaMetadata({
      title: track.title || "Unknown Title",
      artist: track.artist || "Unknown Artist",
      album: track.album || "Unknown Album",
    });
  }, [track]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) {
      return;
    }

    try {
      navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";
    } catch {
      // Ignore.
    }
  }, [isPlaying]);
}
