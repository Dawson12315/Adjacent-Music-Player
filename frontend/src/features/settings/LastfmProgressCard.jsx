function statusLabel(progress) {
  if (progress.is_stopping) return { text: "Stopping...", modifier: "stopping" };
  if (progress.is_running) return { text: "Running", modifier: "running" };
  if (progress.is_stopped) return { text: "Stopped", modifier: "stopped" };
  return { text: "Idle", modifier: "idle" };
}

/** Live progress of the Last.fm genre-enrichment job. */
export function LastfmProgressCard({ progress }) {
  const status = statusLabel(progress);
  const percent = Math.max(0, Math.min(progress.progress_percent || 0, 100));
  const remaining = Math.max(
    (progress.total_tracks || 0) - (progress.processed_tracks || 0),
    0,
  );

  return (
    <div className="lastfm-readiness-card">
      <div className="lastfm-progress-card__header">
        <span className={`lastfm-status-pill lastfm-status-pill--${status.modifier}`}>
          {status.text}
        </span>

        <span className="lastfm-progress-card__batch">
          Batch {progress.current_batch || 0}
        </span>
      </div>

      <div className="lastfm-readiness-card__title">Last.fm enrichment progress</div>

      <div className="lastfm-readiness-card__text">
        Pulling genre tags, similar tracks, and similar artists from Last.fm.
      </div>

      <div className="lastfm-readiness-card__bar">
        <div className="lastfm-readiness-card__bar-fill" style={{ width: `${percent}%` }} />
      </div>

      <div className="lastfm-readiness-card__stats">
        <div className="lastfm-readiness-card__stat">
          <span className="lastfm-readiness-card__label">Processed</span>
          <span className="lastfm-readiness-card__value">
            {progress.processed_tracks || 0}
          </span>
        </div>

        <div className="lastfm-readiness-card__stat">
          <span className="lastfm-readiness-card__label">Remaining</span>
          <span className="lastfm-readiness-card__value">{remaining}</span>
        </div>

        <div className="lastfm-readiness-card__stat">
          <span className="lastfm-readiness-card__label">Total</span>
          <span className="lastfm-readiness-card__value">
            {progress.total_tracks || 0}
          </span>
        </div>

        <div className="lastfm-readiness-card__stat">
          <span className="lastfm-readiness-card__label">Progress</span>
          <span className="lastfm-readiness-card__value">{percent}%</span>
        </div>
      </div>

      <div className="lastfm-progress-card__track">
        <span className="lastfm-progress-card__label">Current track</span>
        <div className="lastfm-progress-card__value">
          {progress.current_title
            ? `${progress.current_index}/${progress.current_total} — ${progress.current_title}`
            : "None"}
        </div>
      </div>

      <div className="lastfm-progress-grid">
        <div className="lastfm-progress-stat">
          <div className="lastfm-progress-stat__label">Tagged</div>
          <div className="lastfm-progress-stat__value">
            {progress.total_processed || 0}
          </div>
        </div>

        <div className="lastfm-progress-stat">
          <div className="lastfm-progress-stat__label">Skipped</div>
          <div className="lastfm-progress-stat__value">{progress.total_skipped || 0}</div>
        </div>

        <div className="lastfm-progress-stat">
          <div className="lastfm-progress-stat__label">Checked</div>
          <div className="lastfm-progress-stat__value">{progress.total_checked || 0}</div>
        </div>
      </div>

      <div className="lastfm-progress-card__footer">
        <span className="lastfm-progress-card__label">Last result</span>
        <span className="lastfm-progress-card__result">
          {progress.last_result || "None"}
        </span>
      </div>
    </div>
  );
}
