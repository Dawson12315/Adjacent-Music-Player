import { List } from "react-window";

import { usePlayer } from "../../contexts/PlayerContext";

/**
 * Declared at module scope on purpose.
 *
 * This component used to be defined inside the root component's body, so it was a new
 * component type on every render — react-window saw `rowComponent` change and unmounted
 * and remounted every visible row, four times a second while a track played. Row data
 * arrives through `rowProps` instead of a closure.
 */
function QueueRow({ index, style, tracks, queueIndex, onJump, onRemove }) {
  const track = tracks[index];

  if (!track) {
    return null;
  }

  const actualIndex = queueIndex + 1 + index;

  return (
    <div style={style}>
      <div className="queue-panel__item queue-panel__item--row">
        <button
          className="queue-panel__item-main"
          onClick={() => onJump(actualIndex)}
          type="button"
        >
          <div className="queue-panel__item-title">{track.title}</div>
          <div className="queue-panel__item-meta">{track.artist || "Unknown Artist"}</div>
        </button>

        <button
          className="queue-panel__remove-button"
          onClick={() => onRemove(actualIndex)}
          type="button"
          aria-label={`Remove ${track.title} from queue`}
        >
          ×
        </button>
      </div>
    </div>
  );
}

export function QueuePanel() {
  const { queue, upcomingQueue, queueIndex, jumpTo, removeFromQueue } = usePlayer();

  const nowPlaying = queueIndex >= 0 ? queue[queueIndex] : null;

  return (
    <aside className="queue-panel">
      <div className="queue-panel__header">
        <h2>Queue</h2>
        <p>{queue.length} tracks</p>
      </div>

      {nowPlaying && (
        <div className="queue-panel__section">
          <div className="queue-panel__section-title">Now Playing</div>

          <button
            className="queue-panel__item queue-panel__item--active"
            onClick={() => jumpTo(queueIndex)}
            type="button"
          >
            <div className="queue-panel__item-title">{nowPlaying.title}</div>
            <div className="queue-panel__item-meta">
              {nowPlaying.artist || "Unknown Artist"}
            </div>
          </button>
        </div>
      )}

      <div className="queue-panel__section queue-panel__section--next">
        <div className="queue-panel__section-title">Next Up</div>

        <div className="queue-panel__list">
          <List
            style={{ width: "100%", height: "100%" }}
            rowCount={upcomingQueue.length}
            rowHeight={88}
            rowComponent={QueueRow}
            rowProps={{
              tracks: upcomingQueue,
              queueIndex,
              onJump: jumpTo,
              onRemove: removeFromQueue,
            }}
          />
        </div>
      </div>
    </aside>
  );
}
