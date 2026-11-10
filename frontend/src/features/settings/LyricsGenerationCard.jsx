import { useState } from "react";

import { usePolling } from "../../hooks/usePolling";
import { getLyricsStatus } from "../../services/lyricsService";
import { describeStatus } from "./lyricsStatus";

const STATUS_POLL_MS = 10000;

/**
 * Settings → Automation → Generate lyrics.
 *
 * The switch for the server producing lyrics from the listener's own audio:
 * timing for words the files already carry, words and timing for tracks with
 * none. Off by default. The card says how much of the library has words,
 * what the worker is doing, and what it costs, so the switch is an informed
 * one. Everything it uses is MIT/BSD/Apache licensed and runs on the server;
 * nothing is sent anywhere (see docs/lyrics.md).
 */
export function LyricsGenerationCard({ settings, updateField, toggleField }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  async function refresh() {
    try {
      setStatus(await getLyricsStatus());
      setError(null);
    } catch (problem) {
      setError(problem?.message || "Could not read the lyrics status.");
    }
  }

  // Read on arrival and every ten seconds while the card is open: the
  // worker's state changes under it, and the first tick is the first read.
  usePolling(refresh, STATUS_POLL_MS, true);

  const line = describeStatus(status, settings.lyrics_generation_enabled);

  return (
    <div className="settings-card">
      <div className="settings-card__title">Generate lyrics</div>
      <div className="settings-card__text">
        Let this server produce lyrics from your own audio: timing for lyrics your files already carry, and words
        for tracks that have none. Runs on the server's CPU when someone opens the lyrics panel, and overnight for your
        most-played tracks. Generated lyrics are labelled as such and may contain errors; an admin can correct them.
      </div>

      <label className="field field--inline">
        <input
          type="checkbox"
          checked={settings.lyrics_generation_enabled}
          onChange={() => toggleField("lyrics_generation_enabled")}
        />
        <span>Enable lyrics generation</span>
      </label>

      <label className="field">
        <span className="field__label">Model</span>
        <select
          className="input"
          value={settings.lyrics_model || "base"}
          onChange={(event) => updateField("lyrics_model", event.target.value)}
        >
          <option value="base">Base — faster, about 300 MB</option>
          <option value="small">Small — more accurate, about 1 GB, three times slower</option>
        </select>
        <span className="field__hint">
          Downloaded once from Hugging Face into the data volume on first use. On a NAS, Base takes about a minute per
          song, Small three to five.
        </span>
      </label>

      <label className="field">
        <span className="field__label">Nightly run time</span>
        <input
          className="input"
          type="time"
          value={settings.lyrics_time}
          onChange={(event) => updateField("lyrics_time", event.target.value)}
        />
        <span className="field__hint">Up to two hours a night on the most-played tracks without lyrics. Leave empty for on-demand only.</span>
      </label>

      {line ? (
        <div className={`watch-status watch-status--${line.tone}`} role="status">
          <span className="watch-status__dot" aria-hidden="true" />
          <span>{line.text}</span>
        </div>
      ) : null}
      {error ? <div className="field__hint">{error}</div> : null}
    </div>
  );
}
