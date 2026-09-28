import { useState } from "react";

import { AccountPanel } from "./AccountPanel";
import { LastfmPanel } from "./LastfmPanel";
import { ServerPanel } from "./ServerPanel";
import { useAppSettings } from "./useAppSettings";
import { useAuth } from "../../contexts/AuthContext";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { useScan } from "../../contexts/ScanContext";
import * as settingsService from "../../services/settingsService";
import { purgeTracks } from "../../services/tracksService";

export function SettingsView() {
  const { notice, notify } = useNotifications();
  const { currentUser } = useAuth();
  const { refreshLibrary, clearTracks } = useLibrary();
  const { clearPlayback } = usePlayer();

  // Regular users manage their own account and nothing else: library
  // maintenance, automation, integrations and the danger zone are the
  // admin's — the API refuses them anyway, so the page doesn't offer them.
  const isAdmin = currentUser?.role === "admin";

  const { settings, updateField, toggleField, save, isSaving } = useAppSettings({
    enabled: isAdmin,
  });

  // Scan progress and polling live in ScanProvider, so the sidebar counts keep
  // updating and the completion toast still fires after navigating away.
  const { progress: scanProgress, isScanning, startScan } = useScan();

  const [confirmAction, setConfirmAction] = useState(null);
  const [isCleaning, setIsCleaning] = useState(false);
  // Set when a cleanup left tracks missing-but-not-yet-removed, or refused a
  // removal above its safety limit: { count, message }. The card then offers
  // to remove them now, which re-runs cleanup with force.
  const [pendingCleanup, setPendingCleanup] = useState(null);

  async function handleScan() {
    if (isScanning) return;

    setConfirmAction(null);

    try {
      await startScan();
    } catch (error) {
      notify(error.message || "Failed to start the library scan.");
    }
  }

  async function handleCleanup(force = false) {
    if (isCleaning) return;

    setIsCleaning(true);

    try {
      const result = await settingsService.runCleanup(force);
      await refreshLibrary();

      const removed = result.removed || 0;
      const outstanding = (result.marked_missing || 0) + (result.still_missing || 0);
      const plural = (count) => (count === 1 ? "" : "s");

      if (removed > 0) {
        notify(`Cleanup removed ${removed} missing track${plural(removed)}.`);
      } else if (outstanding === 0) {
        notify("Cleanup completed. Every track's file is where it should be.");
      } else {
        notify(`Nothing removed yet — ${outstanding} track${plural(outstanding)} missing.`);
      }

      if (!force && outstanding > 0) {
        setPendingCleanup({
          count: outstanding,
          message:
            `${outstanding} track${plural(outstanding)} ${outstanding === 1 ? "has" : "have"} ` +
            `no file right now. ${outstanding === 1 ? "It" : "They"} will be removed ` +
            `automatically after ${result.grace_days} days if still missing — or now, if ` +
            "the files are really gone.",
        });
      } else {
        setPendingCleanup(null);
      }
    } catch (error) {
      if (error.status === 409 && error.detail?.code === "cleanup_refused") {
        const { missing, total } = error.detail;
        setPendingCleanup({
          count: missing,
          message:
            `${missing} of ${total} tracks are missing — more than cleanup removes on ` +
            "its own, because an unmounted drive looks just like this. Remove them anyway?",
        });
      } else {
        notify(error.message || "Failed to run cleanup.");
      }
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

      <ServerPanel />

      {isAdmin && (
      <>
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
                  {isScanning ? "Scanning…" : "Go ahead"}
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
                  {isScanning
                    ? `Scanning… ${(scanProgress?.added ?? 0).toLocaleString()} added`
                    : "Scan library now"}
                </button>
              </div>
            )}
          </div>

          <div className="settings-card">
            <div className="settings-card__title">Run cleanup now</div>
            <div className="settings-card__text">
              Checks every track's file. A track whose file is gone is marked missing and
              removed once it has stayed missing for a week, so a drive that is offline for
              a night costs nothing. Large removals ask first, and a copy of the database is
              saved before anything is removed.
            </div>

            {pendingCleanup ? (
              <>
                <div className="settings-card__text">{pendingCleanup.message}</div>
                <div className="settings-card__actions">
                  <button
                    className="btn"
                    type="button"
                    onClick={() => setPendingCleanup(null)}
                    disabled={isCleaning}
                  >
                    Wait
                  </button>

                  <button
                    className="btn btn--danger"
                    type="button"
                    onClick={() => handleCleanup(true)}
                    disabled={isCleaning}
                  >
                    {isCleaning
                      ? "Removing…"
                      : `Remove ${pendingCleanup.count} now`}
                  </button>
                </div>
              </>
            ) : (
              <div className="settings-card__actions">
                <button
                  className="btn btn--primary"
                  type="button"
                  onClick={() => handleCleanup(false)}
                  disabled={isCleaning}
                >
                  {isCleaning ? "Checking…" : "Run cleanup now"}
                </button>
              </div>
            )}
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
      </>
      )}
    </div>
  );
}
