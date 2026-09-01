/**
 * Shared modal shell. Markup matches the four hand-rolled overlays it replaces, so the
 * existing styles apply unchanged.
 *
 * Dialog semantics — role, focus trapping, Escape to close, focus restoration — are
 * deliberately not added here yet; they are a behaviour change and belong in the
 * accessibility pass. Having one component to add them to is the point of extracting it.
 */
export function Modal({ title, onClose, children, actions }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        {title && (
          <div className="modal__header">
            <h2>{title}</h2>
          </div>
        )}

        <div className="modal__body">{children}</div>

        {actions && <div className="modal__actions">{actions}</div>}
      </div>
    </div>
  );
}
