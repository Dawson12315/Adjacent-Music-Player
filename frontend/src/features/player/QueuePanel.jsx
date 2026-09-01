import { List } from "react-window";

import { Icon } from "../../components/Icon";
import { usePlayer } from "../../contexts/PlayerContext";

/**
 * Declared at module scope on purpose.
 *
 * This used to be defined inside the root component's body, so it was a new component
 * type on every render — react-window saw `rowComponent` change and unmounted and
 * remounted every visible row, four times a second while a track played.
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
          <Icon name="close" size={14} />
        </button>
      </div>
    </div>
  );
}

export function QueuePanel() {
  const { queue, upcomingQueue, queueIndex, isPlaying, jumpTo, removeFromQueue } =
    usePlayer();

  const nowPlaying = queueIndex >= 0 ? queue[queueIndex] : null;

  return (
    <aside className="queue-panel" aria-label="Queue">
      <div className="queue-panel__header">
        <h2>Queue</h2>
        <p>{queue.length.toLocaleString()} tracks</p>
      </div>

      {nowPlaying ? (
        <div className="queue-panel__section">
          <div className="queue-panel__section-title">Now playing</div>

          <div className="queue-panel__item queue-panel__item--active">
            <span className={`eq ${isPlaying ? "" : "eq--paused"}`} aria-hidden="true">
              <span />
              <span />
              <span />
              <span />
            </span>
            <button
              className="queue-panel__item-main"
              onClick={() => jumpTo(queueIndex)}
              type="button"
            >
              <div className="queue-panel__item-title">{nowPlaying.title}</div>
              <div className="queue-panel__item-meta">
                {nowPlaying.artist || "Unknown Artist"}
              </div>
            </button>
          </div>
        </div>
      ) : (
        <div className="state state--inline">
          <p className="state__text">Play something to start a queue.</p>
        </div>
      )}

      <div className="queue-panel__section queue-panel__section--next">
        <div className="queue-panel__section-title">Next up</div>

        {upcomingQueue.length === 0 ? (
          <p className="state__text" style={{ padding: "var(--space-3) 0" }}>
            Nothing queued after this.
          </p>
        ) : (
          <div className="queue-panel__list">
            <List
              style={{ width: "100%", height: "100%" }}
              rowCount={upcomingQueue.length}
              rowHeight={56}
              rowComponent={QueueRow}
              rowProps={{
                tracks: upcomingQueue,
                queueIndex,
                onJump: jumpTo,
                onRemove: removeFromQueue,
              }}
            />
          </div>
        )}
      </div>
    </aside>
  );
}
