import { useState } from "react";

import { AccountPanel } from "./AccountPanel";
import { LastfmPanel } from "./LastfmPanel";
import { useAppSettings } from "./useAppSettings";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer } from "../../contexts/PlayerContext";
import * as settingsService from "../../services/settingsService";
import { purgeTracks } from "../../services/tracksService";

export function SettingsView() {
  const { notice, notify } = useNotifications();
  const { refreshLibrary, clearTracks } = useLibrary();
  const { clearPlayback } = usePlayer();
  const { settings, updateField, toggleField, save, isSaving } = useAppSettings();

  const [confirmAction, setConfirmAction] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isCleaning, setIsCleaning] = useState(false);

  async function handleScan() {
    if (isScanning) return;

    setIsScanning(true);
    setConfirmAction(null);
    notify("Scanning library...");

    try {
      const result = await settingsService.scanLibrary();
      await refreshLibrary();
      notify(
        `Library scan completed. Added ${result.added} new track${
          result.added === 1 ? "" : "s"
        }.`,
      );
    } catch (error) {
      notify(error.message || "Failed to scan the music library.");
    } finally {
      setIsScanning(false);
    }
  }

  async function handleCleanup() {
    if (isCleaning) return;

    setIsCleaning(true);

    try {
      const result = await settingsService.runCleanup();
      await refreshLibrary();
      notify(
        `Cleanup completed. Removed ${result.removed} missing track${
          result.removed === 1 ? "" : "s"
        }.`,
      );
    } catch (error) {
      notify(error.message || "Failed to run cleanup.");
    } finally {
      setIsCleaning(false);
    }
  }

  async function handlePurge() {
    try {
      await purgeTracks();
      clearTracks();
      clearPlayback();
      setConfirmAction(null);
      notify("Stored tracks were purged successfully.");
    } catch (error) {
      setConfirmAction(null);
      notify(error.message || "Failed to purge stored tracks.");
    }
  }

  return (
    <div className="settings-page">
      <div aria-live="polite">
        {notice && <div className="settings-notice">{notice}</div>}
      </div>

      <AccountPanel />

      <section className="settings-section">
        <div className="settings-section__header">
          <h2>Library</h2>
          <p>Scan, clean, and maintain your indexed music library.</p>
        </div>

        <div className="settings-grid settings-grid--two">
          <div className="settings-card">
            <div className="settings-card__title">Scan entire music library</div>
            <div className="settings-card__text">
              Scans your full music library for new files and adds any newly found tracks
              to the database.
            </div>

            {confirmAction === "scan_library" ? (
              <div className="settings-card__actions">
                <button
                  className="btn"
                  type="button"
                  onClick={() => setConfirmAction(null)}
                >
                  Cancel
                </button>

                <button
                  className="btn btn--primary"
                  type="button"
                  onClick={handleScan}
                  disabled={isScanning}
                >
                  {isScanning ? "Scanning..." : "Go ahead"}
                </button>
              </div>
            ) : (
              <div className="settings-card__actions">
                <button
                  className="btn btn--primary"
                  type="button"
                  onClick={() => setConfirmAction("scan_library")}
                  disabled={isScanning}
                >
                  {isScanning ? "Scanning..." : "Scan library now"}
                </button>
              </div>
            )}
          </div>

          <div className="settings-card">
            <div className="settings-card__title">Run cleanup now</div>
            <div className="settings-card__text">
              Immediately remove tracks from the database if their music files no longer
              exist on disk.
            </div>

            <div className="settings-card__actions">
              <button
                className="btn btn--primary"
                type="button"
                onClick={handleCleanup}
                disabled={isCleaning}
              >
                {isCleaning ? "Cleaning..." : "Run cleanup now"}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section__header">
          <h2>Automation</h2>
          <p>Schedule background maintenance jobs.</p>
        </div>

        <div className="settings-grid settings-grid--two">
          <div className="settings-card">
            <div className="settings-card__title">Scan library for new files</div>
            <div className="settings-card__text">
              Scan the music library on a schedule and add newly discovered tracks to the
              database.
            </div>

            <label className="field field--inline">
              <input
                type="checkbox"
                checked={settings.scan_enabled}
                onChange={() => toggleField("scan_enabled")}
              />
              <span>Enable daily scan</span>
            </label>

            <label className="field">
              <span className="field__label">Run time</span>
              <input
                className="input"
                type="time"
                value={settings.scan_time}
                onChange={(event) => updateField("scan_time", event.target.value)}
              />
            </label>
          </div>

          <div className="settings-card">
            <div className="settings-card__title">Cleanup missing files</div>
            <div className="settings-card__text">
              Check whether indexed music files still exist on disk and remove missing
              files from the database and track lists.
            </div>

            <label className="field field--inline">
              <input
                type="checkbox"
                checked={settings.cleanup_enabled}
                onChange={() => toggleField("cleanup_enabled")}
              />
              <span>Enable daily cleanup</span>
            </label>

            <label className="field">
              <span className="field__label">Run time</span>
              <input
                className="input"
                type="time"
                value={settings.cleanup_time}
                onChange={(event) => updateField("cleanup_time", event.target.value)}
              />
            </label>
          </div>
        </div>
      </section>

      <LastfmPanel
        settings={settings}
        updateField={updateField}
        toggleField={toggleField}
      />

      <section className="settings-section">
        <div className="settings-section__header">
          <h2>Danger Zone</h2>
          <p>Destructive actions that affect indexed app data.</p>
        </div>

        <div className="settings-card settings-card--danger">
          <div className="settings-card__title">Purge stored tracks</div>
          <div className="settings-card__text">
            Warning: Removes all indexed tracks from the database and clears playlist
            track entries plus playback state. Music files on the volume will not be
            deleted.
          </div>

          {confirmAction === "purge_tracks" ? (
            <div className="settings-card__actions">
              <button
                className="btn"
                type="button"
                onClick={() => setConfirmAction(null)}
              >
                Cancel
              </button>

              <button
                className="btn btn--danger"
                type="button"
                onClick={handlePurge}
              >
                Go Ahead
              </button>
            </div>
          ) : (
            <div className="settings-card__actions">
              <button
                className="btn btn--danger"
                type="button"
                onClick={() => setConfirmAction("purge_tracks")}
              >
                Purge Database Tracks
              </button>
            </div>
          )}
        </div>
      </section>

      <div className="settings-card__actions settings-card__actions--footer">
        <button
          className="btn btn--primary"
          type="button"
          onClick={save}
          disabled={isSaving}
        >
          {isSaving ? "Saving..." : "Save settings"}
        </button>
      </div>
    </div>
  );
}
