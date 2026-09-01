import { useEffect, useState } from "react";

import { MetadataPicker } from "./MetadataPicker";
import { Modal } from "../../components/Modal";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { TRACK_UPDATED_EVENT } from "../library/useTrackFeed";
import { getArtistTracks, updateTrack } from "../../services/tracksService";

export function EditTrackModal() {
  const { editingTrack, closeTrackEditor, artists, refreshLibrary } = useLibrary();
  const { replaceTrack } = usePlayer();
  const { notify } = useNotifications();

  const [title, setTitle] = useState(editingTrack?.title || "");
  const [artist, setArtist] = useState(editingTrack?.artist || "");
  const [album, setAlbum] = useState(editingTrack?.album || "");
  const [genres, setGenres] = useState((editingTrack?.genres || []).join(", "));
  const [isSaving, setIsSaving] = useState(false);

  /**
   * Only albums that already belong to the selected artist are offered. The
   * library no longer holds every track in memory, so this asks the server
   * for the artist's tracks and derives the album list — previously this read
   * a `tracks` array that no longer exists in LibraryContext, which crashed
   * the whole page the moment the editor opened.
   */
  const [artistAlbums, setArtistAlbums] = useState([]);

  useEffect(() => {
    const cleanedArtist = artist.trim();

    if (!cleanedArtist) {
      setArtistAlbums([]);
      return undefined;
    }

    const controller = new AbortController();

    getArtistTracks(cleanedArtist, { signal: controller.signal })
      .then((rows) => {
        const unique = [...new Set(rows.map((row) => row.album).filter(Boolean))];
        setArtistAlbums(unique);
      })
      .catch((error) => {
        if (error.name !== "AbortError") {
          setArtistAlbums([]);
        }
      });

    return () => controller.abort();
  }, [artist]);

  if (!editingTrack) {
    return null;
  }

  const hasMetadataMismatch =
    (editingTrack.raw_title && editingTrack.raw_title !== editingTrack.title) ||
    (editingTrack.raw_artist && editingTrack.raw_artist !== editingTrack.artist) ||
    (editingTrack.raw_album && editingTrack.raw_album !== editingTrack.album);

  function useRawMetadata() {
    setTitle(editingTrack.raw_title || "");
    setArtist(editingTrack.raw_artist || "");
    setAlbum(editingTrack.raw_album || "");
    setGenres(editingTrack.raw_genre || (editingTrack.genres || []).join(", "));
  }

  async function handleSave() {
    const trimmedTitle = title.trim();

    if (!trimmedTitle) {
      notify("A track needs a title.");
      return;
    }

    setIsSaving(true);

    try {
      const parsedGenres = genres
        .split(",")
        .map((genre) => genre.trim())
        .filter(Boolean);

      // `PATCH /api/tracks/{id}` replaces the whole genre set. Genres are only sent when
      // the editor was seeded from a response that actually carried them — otherwise
      // saving a track opened from a playlist would erase the genres it never received.
      const updated = await updateTrack(editingTrack.id, {
        title: trimmedTitle,
        artist: artist.trim() || null,
        album: album.trim() || null,
        ...(editingTrack.metadataComplete ? { genres: parsedGenres } : {}),
      });

      // The player queue and any mounted track feed patch themselves in
      // place; the modal has no direct handle on either.
      replaceTrack(updated);
      window.dispatchEvent(
        new CustomEvent(TRACK_UPDATED_EVENT, { detail: updated }),
      );

      // Genre/artist/album edits change the *library* lists too (a new genre
      // must appear in the Genres view now, not whenever the next background
      // refresh happens to run). Fire-and-forget; the modal need not wait.
      refreshLibrary().catch(() => {});

      notify("Track info updated.");
      closeTrackEditor();
    } catch (error) {
      notify(error.message || "Failed to update track info.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      title="Edit Info"
      onClose={closeTrackEditor}
      actions={
        <>
          <button
            className="btn"
            type="button"
            onClick={closeTrackEditor}
          >
            Cancel
          </button>

          <button
            className="btn btn--primary"
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
        {hasMetadataMismatch && (
          <div className="modal__warning">
            Metadata was modified during import. Review for accuracy.
          </div>
        )}

        <div className="modal__raw-metadata-title">Original file metadata</div>

        <div className="modal__raw-metadata-row">
          <span className="modal__raw-metadata-label">Raw title:</span>
          <span className="modal__raw-metadata-value">{editingTrack.raw_title || "—"}</span>
        </div>

        <div className="modal__raw-metadata-row">
          <span className="modal__raw-metadata-label">Raw artist:</span>
          <span className="modal__raw-metadata-value">
            {editingTrack.raw_artist || "—"}
          </span>
        </div>

        <div className="modal__raw-metadata-row">
          <span className="modal__raw-metadata-label">Raw album:</span>
          <span className="modal__raw-metadata-value">{editingTrack.raw_album || "—"}</span>
        </div>

        <div className="modal__raw-metadata-actions">
          <button
            className="btn"
            type="button"
            onClick={useRawMetadata}
            disabled={
              !editingTrack.raw_title &&
              !editingTrack.raw_artist &&
              !editingTrack.raw_album
            }
          >
            Use raw values
          </button>
        </div>
      </div>

      <MetadataPicker
        label="Artist"
        value={artist}
        options={artists}
        placeholderLabel="Select artist"
        createPlaceholder="New artist name"
        createButtonLabel="Use artist"
        onChange={setArtist}
      />

      <MetadataPicker
        label="Album"
        value={album}
        options={artistAlbums}
        emptyMessage="No albums found for this artist"
        placeholderLabel="Select album"
        createPlaceholder="New album name"
        createButtonLabel="Use album"
        onChange={setAlbum}
      />

      <label className="field">
        <span className="field__label">Track name</span>
        <input
          className="input"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>

      <label className="field">
        <span className="field__label">Genres</span>
        <input
          className="input"
          type="text"
          value={genres}
          onChange={(event) => setGenres(event.target.value)}
          placeholder="Pop, Dance"
          disabled={!editingTrack.metadataComplete}
        />
      </label>
    </Modal>
  );
}
