import { useCallback, useRef } from "react";

import { usePlayerProgress } from "../../contexts/PlayerContext";
import { formatTime } from "../../utils/format";

const ARROW_STEP_SECONDS = 5;
const PAGE_STEP_SECONDS = 30;

/**
 * The only component that re-renders on a playback tick.
 *
 * It consumes PlayerProgressContext rather than the main player context, which is what
 * keeps `currentTime` updating four times a second from re-rendering the track list, the
 * sidebar and every modal conditional along with it.
 *
 * It is also a real slider: focusable, arrow-key seekable, and reporting its position to
 * assistive technology. Previously a <div role="button"> with a click handler and no key
 * handling at all, so seeking was mouse-only.
 */
export function PlayerProgress() {
  const { currentTime, duration, seek } = usePlayerProgress();
  const trackRef = useRef(null);

  const percent = duration > 0 ? Math.min((currentTime / duration) * 100, 100) : 0;

  const seekToPointer = useCallback(
    (event) => {
      if (!trackRef.current || duration <= 0) return;

      const rect = trackRef.current.getBoundingClientRect();
      const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);

      seek(ratio * duration);
    },
    [duration, seek],
  );

  const handleKeyDown = useCallback(
    (event) => {
      if (duration <= 0) return;

      const moves = {
        ArrowRight: ARROW_STEP_SECONDS,
        ArrowLeft: -ARROW_STEP_SECONDS,
        PageUp: PAGE_STEP_SECONDS,
        PageDown: -PAGE_STEP_SECONDS,
      };

      if (event.key in moves) {
        event.preventDefault();
        seek(Math.min(Math.max(currentTime + moves[event.key], 0), duration));
        return;
      }

      if (event.key === "Home") {
        event.preventDefault();
        seek(0);
      }

      if (event.key === "End") {
        event.preventDefault();
        seek(duration);
      }
    },
    [currentTime, duration, seek],
  );

  return (
    <div className="player-bar__progress-row">
      <span className="player-bar__time">{formatTime(currentTime)}</span>

      <div
        className="player-bar__progress-track"
        ref={trackRef}
        onClick={seekToPointer}
        onKeyDown={handleKeyDown}
        role="slider"
        tabIndex={0}
        aria-label="Seek"
        aria-valuemin={0}
        aria-valuemax={Math.floor(duration) || 0}
        aria-valuenow={Math.floor(currentTime) || 0}
        aria-valuetext={`${formatTime(currentTime)} of ${formatTime(duration)}`}
      >
        <div className="player-bar__progress-fill" style={{ width: `${percent}%` }}>
          <span className="player-bar__progress-thumb" />
        </div>
      </div>

      <span className="player-bar__time">{formatTime(duration)}</span>
    </div>
  );
}
