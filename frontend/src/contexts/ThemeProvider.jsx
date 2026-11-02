import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ThemeContext } from "./ThemeContext";
import { useAuth } from "./AuthContext";
import { useNotifications } from "./NotificationContext";
import {
  DEFAULT_THEME,
  THEME_STORAGE_KEY,
  effectiveTheme,
  nextMidnight,
  preferencesOf,
  themeById,
  themeForDate,
} from "../theme/themes";

/**
 * Dresses the page in the account's theme.
 *
 * The preference lives on the account (theme, whether the seasons may take
 * over, which hemisphere), so every device the listener signs in on wears
 * the same look; this decides what that means today and sets `data-theme`
 * on <html>, which tokens.css reads. Checked on sign-in, when the tab comes
 * back into view, and at the next local midnight while it is open — the
 * moment a window begins. The first time the calendar takes over, one line
 * says so. Adjacent is what an account wears until it says otherwise.
 */
const NOTICED_KEY = "adjacent.theme.noticed";
const FADE_MS = 400;

function readStored(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key, value) {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage can be absent; the theme still applies for the session */
  }
}

export function ThemeProvider({ children, now = () => new Date() }) {
  const { currentUser, updatePreferences } = useAuth();
  const { notify } = useNotifications();

  const prefs = useMemo(() => preferencesOf(currentUser), [currentUser]);

  // A clock the midnight timer and a returning tab both tick; the effective
  // theme is derived from it so a window beginning re-renders the page.
  const [tick, setTick] = useState(0);
  const theme = useMemo(() => effectiveTheme(prefs, now()), [prefs, now, tick]); // eslint-disable-line react-hooks/exhaustive-deps -- `tick` is the clock
  const calendarTheme = useMemo(() => themeForDate(now(), { southern: prefs.southern }), [prefs.southern, now, tick]); // eslint-disable-line react-hooks/exhaustive-deps -- `tick` is the clock

  // Apply: the attribute, the remembered id for the next first paint, and a
  // cross-fade when the change happens under the listener rather than on load.
  const appliedRef = useRef(null);
  useEffect(() => {
    const root = document.documentElement;
    const id = theme.id;
    const previous = appliedRef.current;
    const changingLive = previous != null && previous !== id;
    if (changingLive) root.setAttribute("data-theme-fading", "");
    if (id === DEFAULT_THEME) root.removeAttribute("data-theme");
    else root.dataset.theme = id;
    writeStored(THEME_STORAGE_KEY, id === DEFAULT_THEME ? null : id);
    appliedRef.current = id;
    if (!changingLive) return undefined;
    const timer = setTimeout(() => root.removeAttribute("data-theme-fading"), FADE_MS);
    return () => clearTimeout(timer);
  }, [theme]);

  // The calendar took over: said once per window, and only when the seasons
  // are followed — a theme the listener picked needs no announcement.
  useEffect(() => {
    if (!prefs.seasonal || !currentUser) return;
    if (theme.kind === "year") return;
    const stamp = `${theme.id}:${now().getFullYear()}`;
    if (readStored(NOTICED_KEY) === stamp) return;
    writeStored(NOTICED_KEY, stamp);
    const name = theme.kind === "holiday" ? theme.name : theme.name.toLowerCase();
    notify(`It's ${name} — Adjacent has turned to match. Change it in Settings.`);
  }, [theme, prefs.seasonal, currentUser, notify, now]);

  // Midnight, and coming back to the tab: the day may have changed.
  useEffect(() => {
    if (!prefs.seasonal) return undefined;
    const bump = () => setTick((value) => value + 1);
    const schedule = () => setTimeout(bump, Math.max(1000, nextMidnight(now()).getTime() - now().getTime() + 500));
    let timer = schedule();
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        clearTimeout(timer);
        bump();
        timer = schedule();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [prefs.seasonal, now, tick]);

  /** Settings → Appearance saves through the account, so every device follows. */
  const setPreferences = useCallback(
    (partial) => {
      const body = {};
      if ("theme" in partial) body.theme = partial.theme;
      if ("seasonal" in partial) body.theme_seasonal = partial.seasonal;
      if ("southern" in partial) body.theme_southern = partial.southern;
      return updatePreferences(body);
    },
    [updatePreferences],
  );

  const value = useMemo(
    () => ({
      theme,
      dress: theme.dress || null,
      prefs,
      calendarTheme,
      chosen: themeById(prefs.theme),
      setPreferences,
    }),
    [theme, prefs, calendarTheme, setPreferences],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
