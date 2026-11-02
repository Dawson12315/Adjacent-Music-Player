import { useState } from "react";

import { DuckMark } from "../../components/DuckMark";
import { useTheme } from "../../contexts/ThemeContext";
import { useTransientMessage } from "../../hooks/useTransientMessage";
import { THEMES, windowLabel } from "../../theme/themes";

/**
 * Settings → Appearance: the theme the account wears on every device.
 *
 * Thirteen swatches — Adjacent, four year-round colours, eight that follow
 * the calendar — a switch to let the seasons take over, and one for the
 * southern hemisphere. A seasonal theme picked here is worn all year; with
 * the seasons followed, the pick is what the app wears between them.
 */
export function AppearancePanel() {
  const theming = useTheme();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useTransientMessage();

  if (!theming) return null;
  const { theme, prefs, calendarTheme, setPreferences } = theming;

  async function save(partial) {
    setError("");
    setSaving(true);
    try {
      await setPreferences(partial);
    } catch (saveError) {
      setError(saveError.message || "Could not save the theme.");
    } finally {
      setSaving(false);
    }
  }

  const yearRound = THEMES.filter((item) => item.kind === "year");
  const seasonal = THEMES.filter((item) => item.kind !== "year");

  const swatch = (item) => {
    const picked = prefs.theme === item.id;
    return (
      <button
        key={item.id}
        type="button"
        className={`theme-swatch ${picked ? "theme-swatch--on" : ""}`}
        onClick={() => save({ theme: item.id })}
        disabled={saving}
        aria-pressed={picked}
        aria-label={`${item.name}${item.from ? `, ${windowLabel(item)}` : ""}`}
        title={item.blurb}
      >
        <span className="theme-swatch__dot" style={{ background: item.accent, boxShadow: `0 0 0 3px ${item.ground}` }}>
          {item.dress && (
            <span className="theme-swatch__duck">
              <DuckMark dress={item.dress} title="" />
            </span>
          )}
        </span>
        <span className="theme-swatch__name">{item.name}</span>
        {item.from && <span className="theme-swatch__when">{windowLabel(item)}</span>}
        {item.id === "adjacent" && <span className="theme-swatch__when">default</span>}
      </button>
    );
  };

  return (
    <section className="settings-section">
      <div className="settings-section__header">
        <h2>Appearance</h2>
        <p>The colour the app wears, on every device you sign in on.</p>
      </div>

      <div className="settings-card">
        <div className="settings-card__title">Theme</div>
        <div className="settings-card__text">
          Adjacent is the one it ships with. A seasonal theme can be worn all year, or let the
          calendar choose below. The duck stays yellow whatever you pick.
        </div>

        <div aria-live="polite">{error && <div className="settings-error">{error}</div>}</div>

        <div className="theme-group" role="group" aria-label="Year-round themes">
          <span className="theme-group__label">Year-round</span>
          <div className="theme-swatches">{yearRound.map(swatch)}</div>
        </div>
        <div className="theme-group" role="group" aria-label="Seasonal themes">
          <span className="theme-group__label">With the calendar</span>
          <div className="theme-swatches">{seasonal.map(swatch)}</div>
        </div>

        <div className="theme-row">
          <button
            type="button"
            role="switch"
            aria-checked={prefs.seasonal}
            className={`switch ${prefs.seasonal ? "switch--on" : ""}`}
            onClick={() => save({ seasonal: !prefs.seasonal })}
            disabled={saving}
            aria-label="Follow the seasons"
          >
            <span className="switch__knob" />
          </button>
          <div>
            <div className="theme-row__title">Follow the seasons</div>
            <div className="theme-row__text">
              Spring, summer, autumn, winter — and Halloween, the holidays, New Year and Valentine's
              on their days. Between them the app wears the theme picked above. Right now the calendar
              would wear <strong>{calendarTheme.name}</strong>.
            </div>
          </div>
        </div>

        {prefs.seasonal && (
          <div className="theme-row">
            <button
              type="button"
              role="switch"
              aria-checked={prefs.southern}
              className={`switch ${prefs.southern ? "switch--on" : ""}`}
              onClick={() => save({ southern: !prefs.southern })}
              disabled={saving}
              aria-label="Seasons as in the southern hemisphere"
            >
              <span className="switch__knob" />
            </button>
            <div>
              <div className="theme-row__title">Seasons as in the southern hemisphere</div>
              <div className="theme-row__text">Summer in December, winter in June. The holidays keep their dates.</div>
            </div>
          </div>
        )}

        <div className="theme-wearing">
          Wearing <strong>{theme.name}</strong>
          {prefs.seasonal && theme.id !== prefs.theme ? ` for the season, over ${themeNameOf(prefs.theme)}` : ""}.
        </div>
      </div>
    </section>
  );
}

function themeNameOf(id) {
  return THEMES.find((item) => item.id === id)?.name || "Adjacent";
}
