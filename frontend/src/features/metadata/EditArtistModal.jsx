import { useEffect, useState } from "react";

import { Modal } from "../../components/Modal";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { useArtworkUpload } from "../../hooks/useArtworkUpload";
import { useNavigation } from "../../hooks/useNavigation";
import * as artistsService from "../../services/artistsService";

/**
 * Rename an artist, merge one artist into another, and set the artist banner.
 *
 * Rename and transfer are separate backend operations applied in that order, so a rename
 * plus a transfer moves the renamed artist's tracks. The library is re-read afterwards
 * because both operations rewrite rows across the catalogue.
 */
export function EditArtistModal({ artistName, artworkPath, onClose }) {
  const { artists, refreshLibrary, setArtistArtwork } = useLibrary();
  const { notify } = useNotifications();
  const { goToArtist } = useNavigation();

  const [name, setName] = useState(artistName);
  const [transferTarget, setTransferTarget] = useState("");
  const [isTransferMenuOpen, setIsTransferMenuOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const upload = useArtworkUpload();
  const { setExistingArtwork } = upload;

  useEffect(() => {
    setExistingArtwork(artworkPath);
  }, [artworkPath, setExistingArtwork]);

  async function handleSave() {
    const trimmedName = name.trim();
    const trimmedTarget = transferTarget.trim();

    setIsSaving(true);
    let currentName = artistName;

    try {
      if (trimmedName && trimmedName !== artistName) {
        await artistsService.renameArtist(artistName, trimmedName);
        currentName = trimmedName;
      }

      if (trimmedTarget) {
        await artistsService.transferArtist(currentName, trimmedTarget);
        currentName = trimmedTarget;
      }

      if (upload.file) {
        const result = await artistsService.uploadArtistArtwork(currentName, upload.file);
        setArtistArtwork(currentName, result.artwork_path || "");
      }

      await refreshLibrary();
      onClose();

      if (currentName !== artistName) {
        goToArtist(currentName);
      }
    } catch (error) {
      notify(error.message || "Could not save the artist changes.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      title="Edit Artist"
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
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </>
      }
    >
      <div className="modal__raw-metadata">
        <div className="modal__raw-metadata-title">Artist banner artwork</div>

        {upload.previewUrl ? (
          <img
            className="artist-banner-preview"
            src={upload.previewUrl}
            alt="Artist banner preview"
          />
        ) : (
          <div className="artist-banner-preview artist-banner-preview--empty">
            No artist artwork selected
          </div>
        )}

        <div className="modal__file-row">
          <label className="modal__file-button">
            Choose image
            <input
              className="modal__file-input"
              type="file"
              accept="image/*"
              onChange={upload.selectFile}
            />
          </label>

          <span className="modal__file-name">
            {upload.file ? upload.file.name : "No file selected"}
          </span>
        </div>
      </div>

      <label className="modal__field">
        <span className="modal__label">Rename artist</span>
        <input
          className="modal__input"
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>

      <label className="modal__field">
        <span className="modal__label">Transfer all songs and albums to</span>

        <div className="modal__select-row">
          <button
            className="modal__select"
            type="button"
            onClick={() => setIsTransferMenuOpen((previous) => !previous)}
          >
            {transferTarget || "Select another artist"}
          </button>
        </div>

        {isTransferMenuOpen && (
          <div className="modal__dropdown">
            {artists
              .filter((candidate) => candidate !== artistName)
              .map((candidate) => (
                <button
                  key={candidate}
                  className="modal__dropdown-item"
                  type="button"
                  onClick={() => {
                    setTransferTarget(candidate);
                    setIsTransferMenuOpen(false);
                  }}
                >
                  {candidate}
                </button>
              ))}
          </div>
        )}
      </label>
    </Modal>
  );
}
