import { useCallback, useEffect, useMemo, useState } from "react";

import { AuthContext } from "./AuthContext";
import * as authService from "../services/authService";
import { onUnauthorized } from "../services/apiClient";

/**
 * Owns who is signed in.
 *
 * The important addition over the previous inline version is the `onUnauthorized`
 * subscription: the session cookie lasts seven days, and when it expired the app
 * previously kept rendering a fully-populated but dead UI while every request failed
 * into console.error. Now a 401 from any call returns the user to the sign-in screen.
 */
export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [setupRequired, setSetupRequired] = useState(false);
  // True only when the server was started with SETUP_TOKEN, so the first-run
  // screen knows to ask for it.
  const [setupTokenRequired, setSetupTokenRequired] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadAuthState() {
      try {
        const setupData = await authService.getSetupStatus();

        if (cancelled) return;

        if (!setupData.admin_exists) {
          setSetupRequired(true);
          setSetupTokenRequired(Boolean(setupData.setup_token_required));
          setCurrentUser(null);
          return;
        }

        setSetupRequired(false);

        try {
          const user = await authService.getCurrentUser();
          if (!cancelled) setCurrentUser(user);
        } catch {
          // A 401 here just means "not signed in yet" on first load.
          if (!cancelled) setCurrentUser(null);
        }
      } catch (error) {
        if (!cancelled) {
          setAuthError(error.message || "Authentication failed");
          setCurrentUser(null);
        }
      } finally {
        if (!cancelled) setAuthLoading(false);
      }
    }

    loadAuthState();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(
    () =>
      onUnauthorized(() => {
        setCurrentUser((previous) => {
          if (previous) {
            setSessionExpired(true);
          }

          return null;
        });
      }),
    [],
  );

  const setupAdmin = useCallback(async (username, password, setupToken) => {
    setAuthError("");

    try {
      const user = await authService.setupAdmin(username, password, setupToken);
      setSetupRequired(false);
      setCurrentUser(user);
    } catch (error) {
      setAuthError(error.message || "Unable to create admin account");
      throw error;
    }
  }, []);

  const login = useCallback(async (username, password) => {
    setAuthError("");
    setSessionExpired(false);

    try {
      const user = await authService.login(username, password);
      setCurrentUser(user);
    } catch (error) {
      setAuthError(error.message || "Unable to sign in");
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch (error) {
      // Signing out locally still matters even if the request fails.
      console.error("Logout request failed", error);
    }

    setSessionExpired(false);
    setCurrentUser(null);
  }, []);

  const updateAccount = useCallback(async (payload) => {
    const user = await authService.updateAccount(payload);
    setCurrentUser(user);
    return user;
  }, []);

  const value = useMemo(
    () => ({
      currentUser,
      isAdmin: currentUser?.role === "admin",
      setupRequired,
      setupTokenRequired,
      authLoading,
      authError,
      sessionExpired,
      setupAdmin,
      login,
      logout,
      updateAccount,
    }),
    [
      currentUser,
      setupRequired,
      setupTokenRequired,
      authLoading,
      authError,
      sessionExpired,
      setupAdmin,
      login,
      logout,
      updateAccount,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
