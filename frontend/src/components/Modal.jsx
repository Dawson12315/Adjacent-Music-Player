import { useEffect, useRef } from "react";

import { Icon } from "./Icon";

/**
 * Shared modal shell, with the dialog semantics the four hand-rolled overlays never had:
 * a labelled dialog role, Escape to close, focus moved in on open and restored on close,
 * and Tab trapped inside while it is open.
 */
export function Modal({ title, onClose, children, actions }) {
  const dialogRef = useRef(null);
  const previouslyFocused = useRef(null);

  // Read through a ref so the effect below can run once. It used to depend
  // on onClose, which callers pass inline; every keystroke in a confirm
  // field re-rendered the parent, re-ran the effect, and moved focus to the
  // Close button, so "type migrate to confirm" could not be typed.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    previouslyFocused.current = document.activeElement;

    const dialog = dialogRef.current;
    const focusable = dialog?.querySelector(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );

    (focusable || dialog)?.focus();

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCloseRef.current();
        return;
      }

      if (event.key !== "Tab" || !dialog) {
        return;
      }

      const items = Array.from(
        dialog.querySelectorAll(
          'button:not(:disabled), [href], input:not(:disabled), select, textarea, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((node) => node.offsetParent !== null);

      if (items.length === 0) return;

      const first = items[0];
      const last = items[items.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      previouslyFocused.current?.focus?.();
    };
  }, []);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal__header">
          <h2>{title}</h2>
          <button
            className="modal__close"
            type="button"
            onClick={onClose}
            aria-label="Close"
          >
            <Icon name="close" size={16} />
          </button>
        </div>

        <div className="modal__body">{children}</div>

        {actions && <div className="modal__actions">{actions}</div>}
      </div>
    </div>
  );
}
