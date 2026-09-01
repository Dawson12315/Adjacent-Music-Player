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
    <div className="lastfm-readiness-card">
      <div className="lastfm-readiness-card__title">
        {readiness.musicbrainz_backfill_running
          ? "MusicBrainz tagging is running"
          : "Waiting for MusicBrainz tagging to finish"}
      </div>

      <div className="lastfm-readiness-card__text">
        Last.fm genre enrichment becomes available once every scanned track has been
        processed for MusicBrainz recording IDs.
      </div>

      <div className="lastfm-readiness-card__bar">
        <div
          className="lastfm-readiness-card__bar-fill"
          style={{ width: `${readiness.progress_percent || 0}%` }}
        />
      </div>

      <div className="lastfm-readiness-card__stats">
        <div className="lastfm-readiness-card__stat">
          <span className="lastfm-readiness-card__label">Tagged</span>
          <span className="lastfm-readiness-card__value">{readiness.tracks_with_mbid}</span>
        </div>

        <div className="lastfm-readiness-card__stat">
          <span className="lastfm-readiness-card__label">Remaining</span>
          <span className="lastfm-readiness-card__value">
            {readiness.tracks_missing_mbid}
          </span>
        </div>

        <div className="lastfm-readiness-card__stat">
          <span className="lastfm-readiness-card__label">Total</span>
          <span className="lastfm-readiness-card__value">{readiness.total_tracks}</span>
        </div>

        <div className="lastfm-readiness-card__stat">
          <span className="lastfm-readiness-card__label">Progress</span>
          <span className="lastfm-readiness-card__value">
            {readiness.progress_percent}%
          </span>
        </div>
      </div>

      {canResume && (
        <div className="lastfm-readiness-card__actions">
          <button
            className="settings-button settings-button--secondary"
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
