import { Modal } from "./Modal";

/**
 * Shared upload dialog for playlist and album artwork. Both previously had their own
 * near-identical copy of this markup.
 */
export function ArtworkUploadModal({
  title,
  previewLabel,
  previewUrl,
  fileName,
  onSelectFile,
  onSave,
  onClose,
  isSaving,
}) {
  return (
    <Modal
      title={title}
      onClose={onClose}
      actions={
        <>
          <button
            className="settings-button settings-button--secondary"
            type="button"
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            className="settings-button"
            type="button"
            onClick={onSave}
            disabled={!fileName || isSaving}
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </>
      }
    >
      <label className="modal__field">
        <span className="modal__label">Upload artwork</span>

        <div className="modal__file-row">
          <label className="modal__file-button">
            Choose file
            <input
              className="modal__file-input"
              type="file"
              accept="image/*"
              onChange={onSelectFile}
            />
          </label>

          <span className="modal__file-name">{fileName || "No file selected"}</span>
        </div>
      </label>

      <div className="modal__field">
        <span className="modal__label">Preview</span>

        {previewUrl ? (
          <img
            className="playlist-artwork-preview"
            src={previewUrl}
            alt={`${previewLabel} artwork preview`}
          />
        ) : (
          <div className="playlist-artwork-preview playlist-artwork-preview--empty">
            No artwork selected
          </div>
        )}
      </div>
    </Modal>
  );
}
