/**
 * The Adjacent mark.
 *
 * A real vector, at last — the previous logo was a 290 KB JPEG wrapped in an SVG
 * element, so it could not be recoloured, could not go monochrome, and looked soft at
 * favicon sizes.
 *
 * `tile` draws the blue app-icon square behind the duck; without it the duck stands
 * alone for use against an existing surface.
 */
export function DuckMark({ tile = false, className, title = "Adjacent" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      width="100%"
      height="100%"
      role="img"
      aria-label={title}
      focusable="false"
    >
      {tile && <rect width="32" height="32" rx="7.5" fill="var(--blue-600)" />}

      <g transform="translate(3.8 3.4) scale(0.78)">
        {/* Tail flick, then body, then head — one silhouette from three shapes. */}
        <path d="M3.4 20.6 L1 17.4 L5.2 17.9 Z" fill="var(--yellow)" />
        <path
          d="M4 20.8c0-3.5 4-6 9-6s9 2.5 9 6-4 6-9 6-9-2.5-9-6Z"
          fill="var(--yellow)"
        />
        <circle cx="19.2" cy="12.4" r="5.9" fill="var(--yellow)" />

        <path d="M24.4 10.9 L30.4 12.6 L24.4 14.6 Z" fill="var(--orange)" />
        <circle cx="20.6" cy="11" r="1.25" fill={tile ? "var(--blue-600)" : "var(--field)"} />
      </g>
    </svg>
  );
}
