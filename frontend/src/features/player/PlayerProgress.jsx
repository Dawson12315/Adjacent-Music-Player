import { useRef } from "react";

import { usePlayerProgress } from "../../contexts/PlayerContext";
import { formatTime } from "../../utils/format";

/**
 * The only component that re-renders on a playback tick.
 *
 * It consumes PlayerProgressContext rather than the main player context, which is what
 * keeps `currentTime` updating four times a second from re-rendering the track list, the
 * sidebar and every modal conditional along with it.
 */
export function PlayerProgress() {
  const { currentTime, duration, seek } = usePlayerProgress();
  const trackRef = useRef(null);

  const percent = duration > 0 ? Math.min((currentTime / duration) * 100, 100) : 0;

  function handleSeek(event) {
    if (!trackRef.current || duration <= 0) {
      return;
    }

    const rect = trackRef.current.getBoundingClientRect();
    const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);

    seek(ratio * duration);
  }

  return (
    <div className="player-bar__progress-row">
      <span className="player-bar__time">{formatTime(currentTime)}</span>

      <div
        className="player-bar__progress-track"
        onClick={handleSeek}
        ref={trackRef}
        role="button"
        tabIndex={0}
      >
        <div className="player-bar__progress-fill" style={{ width: `${percent}%` }} />
      </div>

      <span className="player-bar__time">{formatTime(duration)}</span>
    </div>
  );
}
