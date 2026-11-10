import { useState } from "react";

import { usePolling } from "../../hooks/usePolling";
import { analyseNow, getAudioStatus } from "../../services/audioService";
import { describeAudioStatus, describeCoverage } from "./audioStatus";

const STATUS_POLL_MS = 10000;

/**
 * Settings → Automation → Analyse audio.
 *
 * The switch for the server listening to the library for radio: a sound
 * profile per track (tempo, loudness, brightness, timbre) and, with the
 * lyrics model installed, whether a track has vocals, in which language,
 * and whether its words are explicit. On by default; cheap; nothing is sent
 * anywhere (see docs/audio-analysis.md).
 */
export function AudioAnalysisCard({ settings, updateField, toggleField }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  async function refresh() {
    try {
      setStatus(await getAudioStatus());
      setError(null);
    } catch (problem) {
      setError(problem?.message || "Could not read the analysis status.");
    }
  }

  usePolling(refresh, STATUS_POLL_MS, true);

  async function startNow() {
    setStarting(true);
    try {
      await analyseNow();
      await refresh();
    } catch (problem) {
      setError(problem?.message || "Could not start the analysis.");
    } finally {
      setStarting(false);
    }
  }

  const line = describeAudioStatus(status, settings.audio_analysis_enabled);
  const coverage = describeCoverage(status);
  const canStart = Boolean(settings.audio_analysis_enabled && status?.analysis?.enabled && !status?.analysis?.is_running);

  return (
    <div className="settings-card">
      <div className="settings-card__title">Analyse audio</div>
      <div className="settings-card__text">
        Let this server listen to your library so radio can hear what a track sounds like, not only what it is tagged:
        tempo, loudness, brightness and timbre for every track, plus whether it has vocals, in which language, and
        whether the words are explicit. Runs overnight on the most-played tracks first, and after a scan for new
        files. Nothing leaves the server.
      </div>

      <label className="field field--inline">
        <input
          type="checkbox"
          checked={settings.audio_analysis_enabled}
          onChange={() => toggleField("audio_analysis_enabled")}
        />
        <span>Enable audio analysis</span>
      </label>

      <label className="field">
        <span className="field__label">Nightly run time</span>
        <input
          className="input"
          type="time"
          value={settings.audio_analysis_time}
          onChange={(event) => updateField("audio_analysis_time", event.target.value)}
        />
        <span className="field__hint">Up to two hours a night, in a background slot, so a stream always has the CPU first.</span>
      </label>

      {line ? (
        <div className={`watch-status watch-status--${line.tone}`} role="status">
          <span className="watch-status__dot" aria-hidden="true" />
          <span>{line.text}</span>
        </div>
      ) : null}
      {coverage ? <div className="field__hint">{coverage}</div> : null}
      {error ? <div className="field__hint">{error}</div> : null}

      <div className="settings-card__actions">
        <button type="button" className="btn btn--sm" onClick={startNow} disabled={!canStart || starting}>
          {starting ? "Starting…" : "Analyse now"}
        </button>
      </div>
    </div>
  );
}
