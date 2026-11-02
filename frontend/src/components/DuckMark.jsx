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
import { useContext } from "react";

import { ThemeContext } from "../contexts/ThemeContext";

const WAX = "#0B0E14";

// Two grooves, not the half-dozen a real record has: at favicon size more rings stop
// reading as grooves and start reading as moiré.
const GROOVES = [11.6, 9.7];
/**
 * What the duck wears for the season, drawn in the duck's own coordinates
 * so a hat sits the same on the bare bird and on the tile. Accent-coloured
 * parts read `--blue`, which the theme redefines; the rest are fixed, as a
 * real hat's colours would be.
 */
const DRESSES = {
  crown: (
    <g>
      <circle cx="16.15" cy="7.05" r="1.6" fill="#F07CB0" />
      <circle cx="19.36" cy="5.9" r="1.73" fill="#D0B0FF" />
      <circle cx="22.56" cy="6.92" r="1.6" fill="#FFE08A" />
      <circle cx="16.15" cy="7.05" r=".58" fill="#FFF1C8" />
      <circle cx="19.36" cy="5.9" r=".64" fill="#FFF1C8" />
      <circle cx="22.56" cy="6.92" r=".58" fill="#F07CB0" />
    </g>
  ),
  shades: (
    <g>
      <circle cx="21.67" cy="11.28" r="2.56" fill="#0B0E14" />
      <path d="M13.33 9.23 L19.23 10.26" stroke="#0B0E14" strokeWidth="1.03" strokeLinecap="round" />
      <circle cx="20.9" cy="10.38" r=".64" fill="rgba(255,255,255,0.45)" />
    </g>
  ),
  scarf: (
    <g>
      <path d="M13.85 16.67c2.05 1.41 5.51 1.67 8.2.77" stroke="var(--blue)" strokeWidth="2.95" strokeLinecap="round" fill="none" />
      <path d="M15.13 17.95 L13.59 23.33" stroke="var(--blue)" strokeWidth="2.56" strokeLinecap="round" />
      <path d="M13.85 22.82 L13.33 24.62 M14.49 23.33 L14.74 25" stroke="var(--blue)" strokeWidth=".9" strokeLinecap="round" />
    </g>
  ),
  witch: (
    <g>
      <ellipse cx="19.36" cy="7.95" rx="7.18" ry="1.73" fill="#1B1528" />
      <path d="M15.51 7.95 L23.21 7.95 L20.64 -2.31 Z" fill="#1B1528" />
      <path d="M16.15 7.05 L22.56 7.05 L22.05 5.13 L16.79 5.13 Z" fill="var(--blue)" />
      <ellipse cx="19.36" cy="7.95" rx="7.18" ry="1.73" fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth=".3" />
    </g>
  ),
  beanie: (
    <g>
      <path d="M13.59 8.97 Q19.23 0.26 25 8.97 Z" fill="var(--blue-600)" />
      <rect x="13.08" y="7.95" width="12.31" height="2.44" rx="1.15" fill="#F2F4F8" />
      <circle cx="19.36" cy="1.28" r="1.47" fill="#F2F4F8" />
    </g>
  ),
  santa: (
    <g>
      <path d="M14.23 8.46 L23.85 8.46 Q24.1 1.03 26.67 -1.54 Q20 1.28 14.23 8.46 Z" fill="#E8415A" />
      <rect x="13.46" y="7.31" width="11.28" height="2.56" rx="1.28" fill="#F2F4F8" />
      <circle cx="26.79" cy="-1.41" r="1.47" fill="#F2F4F8" />
    </g>
  ),
  party: (
    <g>
      <path d="M16.79 7.95 L22.44 7.95 L19.74 -1.28 Z" fill="var(--blue)" />
      <path d="M17.69 4.87 L21.54 4.87 M18.33 2.56 L20.9 2.56" stroke="#0B0E14" strokeWidth=".9" strokeOpacity=".35" />
      <circle cx="19.74" cy="-1.28" r="1.15" fill="#F2F4F8" />
      <circle cx="10.77" cy="3.59" r=".7" fill="#F07CB0" />
      <circle cx="29.23" cy="3.85" r=".7" fill="#7FB4FF" />
      <circle cx="27.05" cy=".13" r=".58" fill="var(--blue)" />
      <circle cx="9.23" cy="8.46" r=".58" fill="#A76BF0" />
    </g>
  ),
  heart: (
    <g>
      <path d="M10.77 6.03c0-1.41 1.15-2.44 2.44-2.44.9 0 1.54.51 1.92 1.15.38-.64 1.03-1.15 1.92-1.15 1.28 0 2.44 1.03 2.44 2.44 0 2.56-4.36 5-4.36 5S10.77 8.59 10.77 6.03Z" fill="var(--blue)" />
    </g>
  ),
};

/**
 * `dress` names what the duck wears (see DRESSES); left out, it is whatever
 * the theme says, which is nothing on a year-round theme.
 */
export function DuckMark({ tile = false, className, title = "Adjacent", dress }) {
  const theme = useContext(ThemeContext);
  const worn = dress === undefined ? theme?.dress ?? null : dress;
  const overlay = worn ? DRESSES[worn] || null : null;
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
        {overlay && <g data-dress={worn}>{overlay}</g>}
      </g>
    </svg>
  );
}
