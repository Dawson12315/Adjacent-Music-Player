import { Modal } from "./Modal";

/** Shared upload dialog for playlist, album and artist artwork. */
export function ArtworkUploadModal({
  title,
  previewLabel,
  previewUrl,
  fileName,
  onSelectFile,
  onSave,
  onClose,
  isSaving,
  banner = false,
}) {
  return (
    <Modal
      title={title}
      onClose={onClose}
      actions={
        <>
          <button className="btn" type="button" onClick={onClose}>
            Cancel
          </button>

          <button
            className="btn btn--primary"
            type="button"
            onClick={onSave}
            disabled={!fileName || isSaving}
          >
            {isSaving ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <div className="field">
        <span className="field__label">Artwork</span>

        {previewUrl ? (
          <img
            className={`artwork-preview ${banner ? "artwork-preview--banner" : ""}`}
            src={previewUrl}
            alt={`${previewLabel} artwork preview`}
          />
        ) : (
          <div
            className={`artwork-preview artwork-preview--empty ${
              banner ? "artwork-preview--banner" : ""
            }`}
          >
            No artwork selected
          </div>
        )}
      </div>

      <div className="modal__file-row">
        <label className="modal__file-button">
          Choose image
          <input
            className="modal__file-input"
            type="file"
            accept="image/*"
            onChange={onSelectFile}
          />
        </label>

        <span className="modal__file-name">{fileName || "No file selected"}</span>
      </div>
    </Modal>
  );
}
