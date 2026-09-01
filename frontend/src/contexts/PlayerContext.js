import { createContext, useContext } from "react";

export const PlayerContext = createContext(null);

/**
 * Progress is a separate context on purpose: `currentTime` updates about four times a
 * second, and only the progress row consumes it. Keeping it out of the main player
 * context is what stops a playback tick from re-rendering the track list and sidebar.
 */
export const PlayerProgressContext = createContext(null);

export function usePlayer() {
  const context = useContext(PlayerContext);

  if (!context) {
    throw new Error("usePlayer must be used within a PlayerProvider");
  }

  return context;
}

export function usePlayerProgress() {
  const context = useContext(PlayerProgressContext);

  if (!context) {
    throw new Error("usePlayerProgress must be used within a PlayerProvider");
  }

  return context;
}
