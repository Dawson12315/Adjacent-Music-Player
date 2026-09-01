/**
 * MusicBrainz recording IDs have to be filled in before Last.fm genre enrichment can
 * run, so this reports that prerequisite's progress and offers to resume it.
 */
export function MusicbrainzReadinessCard({ readiness, isResuming, onResume }) {
  const canResume =
    readiness.musicbrainz_resume_available &&
    !readiness.musicbrainz_backfill_running &&
    !isResuming;

  return (
    <div className="progress-card">
      <div className="progress-card__title">
        {readiness.musicbrainz_backfill_running
          ? "MusicBrainz tagging is running"
          : "Waiting for MusicBrainz tagging to finish"}
      </div>

      <div className="progress-card__text">
        Last.fm genre enrichment becomes available once every scanned track has been
        processed for MusicBrainz recording IDs.
      </div>

      <div className="progress-bar">
        <div
          className="progress-bar__fill"
          style={{ width: `${readiness.progress_percent || 0}%` }}
        />
      </div>

      <div className="progress-stats">
        <div className="progress-stat">
          <span className="progress-stat__label">Tagged</span>
          <span className="progress-stat__value">{readiness.tracks_with_mbid}</span>
        </div>

        <div className="progress-stat">
          <span className="progress-stat__label">Remaining</span>
          <span className="progress-stat__value">
            {readiness.tracks_missing_mbid}
          </span>
        </div>

        <div className="progress-stat">
          <span className="progress-stat__label">Total</span>
          <span className="progress-stat__value">{readiness.total_tracks}</span>
        </div>

        <div className="progress-stat">
          <span className="progress-stat__label">Progress</span>
          <span className="progress-stat__value">
            {readiness.progress_percent}%
          </span>
        </div>
      </div>

      {canResume && (
        <div className="settings-card__actions">
          <button
            className="btn"
            type="button"
            onClick={onResume}
          >
            Resume MusicBrainz tagging
          </button>
        </div>
      )}
    </div>
  );
}
