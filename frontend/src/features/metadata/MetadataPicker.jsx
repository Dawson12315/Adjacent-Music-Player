import { useState } from "react";

/**
 * The "pick an existing value, or type a new one" control used for both artist and album
 * in the track editor. The two were near-identical copies of forty lines each.
 */
export function MetadataPicker({
  label,
  value,
  options,
  emptyMessage,
  placeholderLabel,
  createPlaceholder,
  createButtonLabel,
  onChange,
}) {
  const [isListOpen, setIsListOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [draft, setDraft] = useState("");

  function reset() {
    setIsListOpen(false);
    setIsCreating(false);
    setDraft("");
  }

  return (
    <label className="field">
      <span className="field__label">{label}</span>

      <div className="modal__select-row">
        <button
          className="modal__select"
          type="button"
          onClick={() => {
            setIsListOpen((previous) => !previous);
            setIsCreating(false);
            setDraft("");
          }}
        >
          {value || placeholderLabel}
        </button>

        <button
          className="btn btn--icon"
          type="button"
          aria-label={createButtonLabel}
          onClick={() => {
            setIsCreating((previous) => !previous);
            setIsListOpen(false);
            setDraft("");
          }}
        >
          +
        </button>
      </div>

      {isListOpen && (
        <div className="modal__dropdown">
          {options.map((option) => (
            <button
              key={option}
              className="modal__dropdown-item"
              type="button"
              onClick={() => {
                onChange(option);
                setIsListOpen(false);
              }}
            >
              {option}
            </button>
          ))}

          {options.length === 0 && emptyMessage && (
            <div className="modal__dropdown-empty">{emptyMessage}</div>
          )}
        </div>
      )}

      {isCreating && (
        <div className="modal__inline-create">
          <input
            className="input"
            type="text"
            placeholder={createPlaceholder}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />

          <div className="modal__inline-actions">
            <button
              className="btn"
              type="button"
              onClick={reset}
            >
              Cancel
            </button>

            <button
              className="btn btn--primary"
              type="button"
              onClick={() => {
                const trimmed = draft.trim();
                if (!trimmed) return;

                onChange(trimmed);
                reset();
              }}
            >
              {createButtonLabel}
            </button>
          </div>
        </div>
      )}
    </label>
  );
}
