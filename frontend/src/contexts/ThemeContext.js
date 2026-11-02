import { createContext, useContext } from "react";

/**
 * The theme the app wears: `{ theme, dress, prefs, setPreferences,
 * calendarTheme }`. Null outside the provider — the duck then wears
 * nothing, which is the default anyway.
 */
export const ThemeContext = createContext(null);

export function useTheme() {
  return useContext(ThemeContext);
}
