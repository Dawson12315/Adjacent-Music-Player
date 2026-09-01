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
    <div className="progress-card">
      <div className="progress-card__header">
        <span className={`pill pill--${status.modifier}`}>
          {status.text}
        </span>

        <span className="progress-card__text">
          Batch {progress.current_batch || 0}
        </span>
      </div>

      <div className="progress-card__title">Last.fm enrichment progress</div>

      <div className="progress-card__text">
        Pulling genre tags, similar tracks, and similar artists from Last.fm.
      </div>

      <div className="progress-bar">
        <div className="progress-bar__fill" style={{ width: `${percent}%` }} />
      </div>

      <div className="progress-stats">
        <div className="progress-stat">
          <span className="progress-stat__label">Processed</span>
          <span className="progress-stat__value">
            {progress.processed_tracks || 0}
          </span>
        </div>

        <div className="progress-stat">
          <span className="progress-stat__label">Remaining</span>
          <span className="progress-stat__value">{remaining}</span>
        </div>

        <div className="progress-stat">
          <span className="progress-stat__label">Total</span>
          <span className="progress-stat__value">
            {progress.total_tracks || 0}
          </span>
        </div>

        <div className="progress-stat">
          <span className="progress-stat__label">Progress</span>
          <span className="progress-stat__value">{percent}%</span>
        </div>
      </div>

      <div className="progress-card__text">
        <span className="progress-stat__label">Current track</span>
        <div className="progress-stat__value">
          {progress.current_title
            ? `${progress.current_index}/${progress.current_total} — ${progress.current_title}`
            : "None"}
        </div>
      </div>

      <div className="progress-stats">
        <div className="progress-stat">
          <div className="progress-stat__label">Tagged</div>
          <div className="progress-stat__value">
            {progress.total_processed || 0}
          </div>
        </div>

        <div className="progress-stat">
          <div className="progress-stat__label">Skipped</div>
          <div className="progress-stat__value">{progress.total_skipped || 0}</div>
        </div>

        <div className="progress-stat">
          <div className="progress-stat__label">Checked</div>
          <div className="progress-stat__value">{progress.total_checked || 0}</div>
        </div>
      </div>

      <div className="progress-card__header">
        <span className="progress-stat__label">Last result</span>
        <span className="progress-stat__value">
          {progress.last_result || "None"}
        </span>
      </div>
    </div>
  );
}
