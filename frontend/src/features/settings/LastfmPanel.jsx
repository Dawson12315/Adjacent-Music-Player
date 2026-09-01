import { useCallback, useEffect, useState } from "react";

import { LastfmProgressCard } from "./LastfmProgressCard";
import { MusicbrainzReadinessCard } from "./MusicbrainzReadinessCard";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePolling } from "../../hooks/usePolling";
import * as settingsService from "../../services/settingsService";

const PROGRESS_POLL_MS = 4000;
const READINESS_POLL_MS = 2500;

const EMPTY_READINESS = {
  total_tracks: 0,
  tracks_with_mbid: 0,
  tracks_missing_mbid: 0,
  progress_percent: 0,
  ready: false,
  musicbrainz_backfill_running: false,
  musicbrainz_resume_available: false,
};

/**
 * Last.fm connection, genre enrichment, and the MusicBrainz tagging that has to finish
 * before enrichment can start.
 *
 * Both progress readouts poll only while their job is actually running; the intervals are
 * owned by usePolling rather than by refs cleared from several places.
 */
export function LastfmPanel({ settings, updateField, toggleField }) {
  const { notify } = useNotifications();

  const [readiness, setReadiness] = useState(EMPTY_READINESS);
  const [progress, setProgress] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isResumingMusicbrainz, setIsResumingMusicbrainz] = useState(false);

  const isEnriching = Boolean(progress?.is_running || progress?.is_stopping);

  const fetchProgress = useCallback(async () => {
    try {
      setProgress(await settingsService.getLastfmProgress());
    } catch (error) {
      console.error("Failed to read Last.fm progress", error);
    }
  }, []);

  const fetchReadiness = useCallback(async () => {
    try {
      const data = await settingsService.getLastfmReadiness();
      setReadiness(data);

      if (!data.musicbrainz_backfill_running) {
        setIsResumingMusicbrainz(false);
      }
    } catch (error) {
      console.error("Failed to read Last.fm readiness", error);
    }
  }, []);

  useEffect(() => {
    fetchProgress();
    fetchReadiness();
  }, [fetchProgress, fetchReadiness]);

  usePolling(fetchProgress, PROGRESS_POLL_MS, isEnriching);
  usePolling(
    fetchReadiness,
    READINESS_POLL_MS,
    readiness.musicbrainz_backfill_running || isResumingMusicbrainz,
  );

  async function handleConnect() {
    if (!settings.lastfm_api_key.trim()) {
      notify("Save your Last.fm API key first.");
      return;
    }

    setIsConnecting(true);

    try {
      const callbackUrl = `${window.location.origin}/settings/lastfm/callback`;
      const data = await settingsService.getLastfmAuthUrl(callbackUrl);

      if (!data.auth_url) {
        throw new Error("Missing Last.fm auth URL");
      }

      window.location.href = data.auth_url;
    } catch (error) {
      notify(error.message || "Failed to start Last.fm connection.");
      setIsConnecting(false);
    }
  }

  async function handleStartEnrichment() {
    notify("Starting Last.fm enrichment...");

    try {
      const result = await settingsService.startLastfmEnrichment();

      if (result.reason === "already_running") {
        notify("Last.fm enrichment is already running.");
      } else if (result.started) {
        notify("Last.fm enrichment started.");
      } else {
        throw new Error("Last.fm enrichment did not start");
      }

      await fetchProgress();
    } catch (error) {
      notify(error.message || "Failed to start Last.fm enrichment.");
    }
  }

  async function handleStopEnrichment() {
    // Reflect the stop immediately; the next poll confirms it.
    setProgress((previous) =>
      previous ? { ...previous, is_stopping: true, last_result: "stop_requested" } : previous,
    );

    try {
      await settingsService.stopLastfmEnrichment();
      notify("Stopping Last.fm genre enrichment...");
      await fetchProgress();
    } catch (error) {
      notify(error.message || "Failed to stop enrichment.");
    }
  }

  async function handleResumeMusicbrainz() {
    setIsResumingMusicbrainz(true);

    try {
      const result = await settingsService.resumeMusicbrainzBackfill();

      if (result.reason === "already_running") {
        notify("MusicBrainz tagging is already running.");
      } else if (result.reason === "nothing_to_resume") {
        notify("No unfinished MusicBrainz tagging work was found.");
        setIsResumingMusicbrainz(false);
      } else if (result.started) {
        notify("MusicBrainz tagging resumed.");
      } else {
        notify("MusicBrainz tagging could not be resumed.");
        setIsResumingMusicbrainz(false);
      }

      await fetchReadiness();
    } catch (error) {
      notify(error.message || "Failed to resume MusicBrainz tagging.");
      setIsResumingMusicbrainz(false);
    }
  }

  return (
    <section className="settings-section">
      <div className="settings-section__header">
        <h2>Last.fm</h2>
        <p>Connect scrobbling, genre enrichment, similar artists, and similar tracks.</p>
      </div>

      <div className="settings-card settings-card--wide">
        <div className="settings-card__title">Last.fm Integration</div>
        <div className="settings-card__text">
          Paste your Last.fm API key and shared secret, press "Save settings", then press
          "Connect Last.fm", to enable genre-tag enrichment from Last.fm and scrobbling.
          Only do this once your library scan import and MusicBrainz tagging is complete.
        </div>

        <div className="settings-grid settings-grid--two">
          <label className="field">
            <span className="field__label">Last.fm API key</span>
            <input
              className="input"
              type="text"
              value={settings.lastfm_api_key}
              onChange={(event) => updateField("lastfm_api_key", event.target.value)}
              placeholder="Enter Last.fm API key"
            />
          </label>

          <label className="field">
            <span className="field__label">Last.fm API secret</span>
            <input
              className="input"
              type="password"
              autoComplete="off"
              value={settings.lastfm_api_secret}
              onChange={(event) => updateField("lastfm_api_secret", event.target.value)}
              placeholder={
                settings.lastfm_api_secret_set
                  ? "Saved — enter a new secret to replace it"
                  : "Enter Last.fm API secret"
              }
            />
          </label>
        </div>

        <div className="settings-card__text settings-card__text">
          {settings.lastfm_username
            ? `Connected as ${settings.lastfm_username}`
            : "Not connected to Last.fm yet."}
        </div>

        <div className="settings-card__actions">
          <button
            className="btn"
            type="button"
            onClick={handleConnect}
            disabled={
              isConnecting ||
              !settings.lastfm_api_key.trim() ||
              !(settings.lastfm_api_secret.trim() || settings.lastfm_api_secret_set)
            }
          >
            {isConnecting ? "Connecting..." : "Connect Last.fm"}
          </button>

          {readiness.ready && (
            <button
              className="btn btn--primary"
              type="button"
              onClick={handleStartEnrichment}
              disabled={isEnriching || !settings.lastfm_api_key.trim()}
            >
              {isEnriching ? "Enriching..." : "Start Last.fm enrichment"}
            </button>
          )}

          {isEnriching && (
            <button
              className="btn btn--danger"
              type="button"
              onClick={handleStopEnrichment}
            >
              Stop
            </button>
          )}
        </div>

        {!readiness.ready && (
          <MusicbrainzReadinessCard
            readiness={readiness}
            isResuming={isResumingMusicbrainz}
            onResume={handleResumeMusicbrainz}
          />
        )}

        {progress && <LastfmProgressCard progress={progress} />}

        <div className="settings-grid settings-grid--two">
          <label className="field field--inline">
            <input
              type="checkbox"
              checked={settings.lastfm_enrichment_enabled}
              onChange={() => toggleField("lastfm_enrichment_enabled")}
            />
            <span>Enable daily Last.fm enrichment</span>
          </label>

          <label className="field">
            <span className="field__label">Run time</span>
            <input
              className="input"
              type="time"
              value={settings.lastfm_enrichment_time}
              onChange={(event) =>
                updateField("lastfm_enrichment_time", event.target.value)
              }
            />
          </label>
        </div>
      </div>
    </section>
  );
}
