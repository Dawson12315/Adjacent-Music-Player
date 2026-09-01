/**
 * The icon set.
 *
 * Replaces seven 1024px photographic PNGs — 6.5 MB in total, rendered at about 40px —
 * that spanned five unrelated colour families and mixed filled and outlined styles at
 * random. These are one geometric family: a 24px grid, 1.75 stroke, round caps and
 * joins, drawn in `currentColor` so they inherit whatever the surface needs.
 *
 * Solid glyphs (play, pause, the filled heart) are deliberate exceptions — a transport
 * control needs the visual weight.
 */

const STROKE = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

const SOLID = { fill: "currentColor", stroke: "none" };

const icons = {
  /* ---------- navigation ---------- */
  home: (
    <>
      <path {...STROKE} d="M3.5 10.5 12 3.5l8.5 7" />
      <path {...STROKE} d="M5.5 9.5v10h13v-10" />
      <path {...STROKE} d="M9.75 19.5v-5.25h4.5v5.25" />
    </>
  ),
  tracks: (
    <>
      <path {...STROKE} d="M9 18V5.5l10-2V16" />
      <circle {...STROKE} cx="6.75" cy="18" r="2.25" />
      <circle {...STROKE} cx="16.75" cy="16" r="2.25" />
    </>
  ),
  artists: (
    <>
      <circle {...STROKE} cx="12" cy="8" r="3.75" />
      <path {...STROKE} d="M4.75 20c0-3.5 3.25-5.75 7.25-5.75s7.25 2.25 7.25 5.75" />
    </>
  ),
  albums: (
    <>
      <circle {...STROKE} cx="12" cy="12" r="8.5" />
      <circle {...STROKE} cx="12" cy="12" r="2.75" />
    </>
  ),
  genres: (
    <>
      <path {...STROKE} d="M4 6.5h9M4 12h9M4 17.5h6" />
      <path {...STROKE} d="M17.5 17V8l3.5-.75" />
      <circle {...STROKE} cx="16" cy="17.5" r="1.75" />
    </>
  ),
  insights: (
    <>
      <path {...STROKE} d="M4 20V4" />
      <path {...STROKE} d="M4 20h16" />
      <path {...STROKE} d="M8 16.5v-4M12 16.5v-8M16 16.5v-6" />
    </>
  ),
  settings: (
    <>
      <path {...STROKE} d="M5 7.5h14M5 16.5h14" />
      <circle {...STROKE} cx="9.5" cy="7.5" r="2.25" />
      <circle {...STROKE} cx="15" cy="16.5" r="2.25" />
    </>
  ),

  /* ---------- transport ---------- */
  play: <path {...SOLID} d="M8 5.5v13l11-6.5z" />,
  pause: (
    <>
      <rect {...SOLID} x="7" y="5.5" width="3.5" height="13" rx="1.25" />
      <rect {...SOLID} x="13.5" y="5.5" width="3.5" height="13" rx="1.25" />
    </>
  ),
  previous: (
    <>
      <path {...SOLID} d="M18 6v12l-9-6z" />
      <rect {...SOLID} x="5" y="6" width="2.5" height="12" rx="1" />
    </>
  ),
  next: (
    <>
      <path {...SOLID} d="M6 6v12l9-6z" />
      <rect {...SOLID} x="16.5" y="6" width="2.5" height="12" rx="1" />
    </>
  ),
  shuffle: (
    <>
      <path {...STROKE} d="M3.5 7h3.2c1.4 0 2.2.8 3.1 2l4 6c.9 1.2 1.7 2 3.1 2h3.6" />
      <path {...STROKE} d="M3.5 17h3.2c1.4 0 2.2-.8 3.1-2" />
      <path {...STROKE} d="M14 9c.9-1.2 1.7-2 3.1-2h3.4" />
      <path {...STROKE} d="m18.2 4.6 2.3 2.4-2.3 2.4M18.2 14.6l2.3 2.4-2.3 2.4" />
    </>
  ),
  repeat: (
    <>
      <path {...STROKE} d="M6.5 8.5h11a2.5 2.5 0 0 1 2.5 2.5v1" />
      <path {...STROKE} d="M17.5 15.5h-11A2.5 2.5 0 0 1 4 13v-1" />
      <path {...STROKE} d="m8.6 6 -2.4 2.5L8.6 11M15.4 13l2.4 2.5-2.4 2.5" />
    </>
  ),
  queue: (
    <>
      <path {...STROKE} d="M4 7h11M4 12h11M4 17h7" />
      <path {...STROKE} d="M18 10v7.5" />
      <circle {...STROKE} cx="16.5" cy="18" r="1.5" />
    </>
  ),
  volume: (
    <>
      <path {...STROKE} d="M4.5 9.5h3L11.5 6v12L7.5 14.5h-3z" />
      <path {...STROKE} d="M15 9.5a3.5 3.5 0 0 1 0 5M17.5 7a7 7 0 0 1 0 10" />
    </>
  ),
  volumeMute: (
    <>
      <path {...STROKE} d="M4.5 9.5h3L11.5 6v12L7.5 14.5h-3z" />
      <path {...STROKE} d="m15.5 9.5 4.5 5M20 9.5l-4.5 5" />
    </>
  ),
  heart: (
    <path
      {...STROKE}
      d="M12 19.5S4.5 15 4.5 9.9A3.9 3.9 0 0 1 12 8a3.9 3.9 0 0 1 7.5 1.9c0 5.1-7.5 9.6-7.5 9.6Z"
    />
  ),
  heartFilled: (
    <path
      {...SOLID}
      d="M12 19.5S4.5 15 4.5 9.9A3.9 3.9 0 0 1 12 8a3.9 3.9 0 0 1 7.5 1.9c0 5.1-7.5 9.6-7.5 9.6Z"
    />
  ),

  /* ---------- interface ---------- */
  search: (
    <>
      <circle {...STROKE} cx="11" cy="11" r="6.25" />
      <path {...STROKE} d="m16 16 4 4" />
    </>
  ),
  plus: <path {...STROKE} d="M12 5.5v13M5.5 12h13" />,
  close: <path {...STROKE} d="m6.5 6.5 11 11M17.5 6.5l-11 11" />,
  more: (
    <>
      <circle {...SOLID} cx="6" cy="12" r="1.6" />
      <circle {...SOLID} cx="12" cy="12" r="1.6" />
      <circle {...SOLID} cx="18" cy="12" r="1.6" />
    </>
  ),
  chevronRight: <path {...STROKE} d="m9.5 5.5 6.5 6.5-6.5 6.5" />,
  chevronLeft: <path {...STROKE} d="M14.5 5.5 8 12l6.5 6.5" />,
  menu: <path {...STROKE} d="M4 7h16M4 12h16M4 17h16" />,
  refresh: (
    <>
      <path {...STROKE} d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" />
      <path {...STROKE} d="M19.5 4v4h-4" />
    </>
  ),
  clock: (
    <>
      <circle {...STROKE} cx="12" cy="12" r="8" />
      <path {...STROKE} d="M12 7.5V12l3 2" />
    </>
  ),
  skip: (
    <>
      <path {...STROKE} d="M5 12h11" />
      <path {...STROKE} d="m12.5 8 4 4-4 4" />
      <path {...STROKE} d="M19.5 7v10" />
    </>
  ),
  sparkle: (
    <path
      {...STROKE}
      d="M12 4.5c0 3.6 1.9 5.5 5.5 5.5-3.6 0-5.5 1.9-5.5 5.5 0-3.6-1.9-5.5-5.5-5.5 3.6 0 5.5-1.9 5.5-5.5Z"
    />
  ),
  music: (
    <>
      <path {...STROKE} d="M9 17V6l9-1.75V15" />
      <circle {...STROKE} cx="6.75" cy="17.25" r="2.25" />
      <circle {...STROKE} cx="15.75" cy="15.25" r="2.25" />
    </>
  ),
};

export function Icon({ name, size = 20, className, title }) {
  const glyph = icons[name];

  if (!glyph) {
    return null;
  }

  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      role={title ? "img" : "presentation"}
      aria-label={title}
      aria-hidden={title ? undefined : "true"}
      focusable="false"
    >
      {glyph}
    </svg>
  );
}
