import { memo, useContext } from "react";

import { ThemeContext } from "../contexts/ThemeContext";
import { DEFAULT_THEME } from "../theme/themes";
import { DuckMark } from "./DuckMark";

/**
 * Renders an artwork descriptor from utils/artwork — a real cover, a generated tile, or
 * the duck for the system playlist.
 *
 * Images are lazy by default and always carry explicit dimensions, so off-screen covers
 * are not downloaded and the layout does not shift as they arrive. Initials scale from
 * the tile's own font-size, which is why every call site sets one.
 */
export const Artwork = memo(function Artwork({
  artwork,
  className = "",
  eager = false,
  size,
}) {
  const classes = ["art", className].filter(Boolean).join(" ");
  // A worn theme puts the duck on its own accent, where yellow has less edge
  // than on the default blue; a thin line keeps the bird legible at cover size.
  const theming = useContext(ThemeContext);
  const outlined = Boolean(theming?.theme && theming.theme.id !== DEFAULT_THEME);

  if (!artwork) {
    return <div className={classes} aria-hidden="true" />;
  }

  if (artwork.type === "duck") {
    return (
      <div className={`${classes} art--duck`} style={{ background: "var(--blue-600)" }}>
        <DuckMark title={artwork.alt || "Ducking Good"} outline={outlined} />
      </div>
    );
  }

  if (artwork.type === "image") {
    return (
      <div className={classes}>
        <img
          src={artwork.src}
          alt=""
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          width={size}
          height={size}
        />
      </div>
    );
  }

  return (
    <div className={`${classes} art--generated art--${artwork.tone}`} aria-hidden="true">
      <span className="art__initials">{artwork.initials}</span>
    </div>
  );
});
