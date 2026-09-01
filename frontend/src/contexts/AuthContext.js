import { createContext, useContext } from "react";

/**
 * Context object and consumer hook.
 *
 * Kept apart from the provider component so each module exports one kind of thing, which
 * is what lets Fast Refresh reload the provider without dropping application state.
 */
export const AuthContext = createContext(null);

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}
