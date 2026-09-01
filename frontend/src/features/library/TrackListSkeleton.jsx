/**
 * Structure while loading, instead of the word "Loading".
 *
 * Matching the real row layout means the page does not jump when the data lands, and the
 * shape tells you what is about to appear.
 */
export function TrackListSkeleton({ rows = 10 }) {
  return (
    <div className="track-list" aria-busy="true" aria-label="Loading tracks">
      {Array.from({ length: rows }, (_, index) => (
        <div className="track-skeleton" key={index}>
          <div className="skeleton skeleton--text" style={{ width: 14 }} />
          <div className="skeleton track-skeleton__art" />
          <div className="track-skeleton__lines">
            <div
              className="skeleton skeleton--title"
              style={{ width: `${45 + ((index * 13) % 35)}%` }}
            />
            <div
              className="skeleton skeleton--text"
              style={{ width: `${28 + ((index * 7) % 22)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Card-shaped skeleton for the home rails and entity grids. */
export function CardGridSkeleton({ count = 6, className = "entity-grid" }) {
  return (
    <div className={className} aria-busy="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} style={{ padding: "var(--space-3)" }}>
          <div
            className="skeleton"
            style={{ width: "100%", aspectRatio: 1, borderRadius: "var(--radius-sm)" }}
          />
          <div
            className="skeleton skeleton--title"
            style={{ marginTop: "var(--space-3)" }}
          />
          <div
            className="skeleton skeleton--text"
            style={{ marginTop: "var(--space-2)", width: "40%" }}
          />
        </div>
      ))}
    </div>
  );
}
