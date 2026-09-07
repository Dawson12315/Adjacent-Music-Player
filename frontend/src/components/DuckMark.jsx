/**
 * The Adjacent mark.
 *
 * A real vector, at last — the previous logo was a 290 KB JPEG wrapped in an SVG
 * element, so it could not be recoloured, could not go monochrome, and looked soft at
 * favicon sizes.
 *
 * `tile` draws the app icon: the blue square, a record, and the duck on top of it — the
 * same artwork the favicon and the mobile client's launcher icon are drawn from, so the
 * three cannot drift apart.
 *
 * Without `tile` the duck stands alone, for use against an existing surface. That is
 * deliberately still a bare duck: it is what Ducking Good wears as its cover, and a
 * record inside a playlist tile would be a picture of a record, not a playlist.
 */

/**
 * The record. Near-black with a little blue in it rather than pure black, which against
 * the blue tile reads as a hole punched in the icon.
 */
const WAX = "#0B0E14";

// Two grooves, not the half-dozen a real record has: at favicon size more rings stop
// reading as grooves and start reading as moiré.
const GROOVES = [11.6, 9.7];
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

      {tile && (
        <>
          <circle cx="16" cy="16" r="13.2" fill={WAX} />
          {GROOVES.map((r) => (
            <circle
              key={r}
              cx="16"
              cy="16"
              r={r}
              fill="none"
              stroke="rgba(255,255,255,0.12)"
              strokeWidth="0.14"
            />
          ))}
          <circle
            cx="16"
            cy="16"
            r="13.2"
            fill="none"
            stroke="rgba(255,255,255,0.18)"
            strokeWidth="0.2"
          />
        </>
      )}

      {/* Centred on the record when there is one, and a little smaller, so the grooves
          read around the bird instead of being covered by it. */}
      <g
        transform={
          tile ? "translate(5.638 5.611) scale(0.66)" : "translate(3.8 3.4) scale(0.78)"
        }
      >
        {/* Tail flick, then body, then head — one silhouette from three shapes. */}
        <path d="M3.4 20.6 L1 17.4 L5.2 17.9 Z" fill="var(--yellow)" />
        <path
          d="M4 20.8c0-3.5 4-6 9-6s9 2.5 9 6-4 6-9 6-9-2.5-9-6Z"
          fill="var(--yellow)"
        />
        <circle cx="19.2" cy="12.4" r="5.9" fill="var(--yellow)" />

        <path d="M24.4 10.9 L30.4 12.6 L24.4 14.6 Z" fill="var(--orange)" />
        {/* Punched through to whatever sits behind: the record when there is one, the
            page ground when the duck stands alone. */}
        <circle cx="20.6" cy="11" r="1.25" fill={tile ? WAX : "var(--field)"} />
      </g>
    </svg>
  );
}
