import { Icon } from "./Icon";

/**
 * The app's one notice, made visible.
 *
 * Notices used to render only into a visually-hidden live region, so every
 * playback error, "last track", "could not add" and handoff message reached
 * screen readers and nobody else. This is the same message, on screen, above
 * the player bar, dismissable, still announced through the live region.
 */
export function Toast({ notice, onDismiss }) {
  return (
    <div className="toast-region" role="status" aria-live="polite">
      {notice && (
        <div className="toast">
          <span className="toast__text">{notice}</span>
          <button
            className="btn btn--icon btn--ghost toast__close"
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss"
          >
            <Icon name="close" size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
