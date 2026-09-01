import { useState } from "react";

import { useAuth } from "../../contexts/AuthContext";
import { recoverPassword } from "../../services/authService";

/**
 * Sign-in, first-run admin setup, and recovery-code password reset.
 *
 * Markup and class names are unchanged from the original inline version so the existing
 * stylesheet applies as-is.
 */
export function AuthScreen({ mode }) {
  const { login, setupAdmin, authError, sessionExpired } = useAuth();

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [isRecoveringPassword, setIsRecoveringPassword] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [recoveryError, setRecoveryError] = useState("");
  const [recoverySuccess, setRecoverySuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isSetup = mode === "setup";

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      if (isSetup) {
        await setupAdmin(username, password);
      } else {
        await login(username, password);
      }
    } catch (error) {
      // AuthContext surfaces the message through authError.
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRecoverPassword(event) {
    event.preventDefault();

    setRecoveryError("");
    setRecoverySuccess("");
    setIsSubmitting(true);

    try {
      await recoverPassword({
        username,
        recoveryCode,
        newPassword,
        confirmPassword,
      });

      setRecoverySuccess("Password reset successfully. You can now sign in.");
      setPassword("");
      setRecoveryCode("");
      setNewPassword("");
      setConfirmPassword("");
      setIsRecoveringPassword(false);
    } catch (error) {
      setRecoveryError(error.message || "Failed to reset password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo-wrap">
          <img className="auth-logo" src="/Adjacent.svg" alt="Adjacent logo" />
        </div>

        <div className="auth-brand">Adjacent</div>

        <h1 className="auth-title">
          {isSetup
            ? "Create admin account"
            : isRecoveringPassword
            ? "Recover password"
            : "Welcome back"}
        </h1>

        <p className="auth-subtitle">
          {isSetup
            ? "Create the first admin account to secure your music library."
            : isRecoveringPassword
            ? "Use one of your saved recovery codes to reset your password."
            : "Sign in to continue to your music library."}
        </p>

        <div aria-live="polite">
          {sessionExpired && !isRecoveringPassword && (
            <div className="auth-error">Your session expired. Please sign in again.</div>
          )}
          {authError && !isRecoveringPassword && <div className="auth-error">{authError}</div>}
          {recoveryError && <div className="auth-error">{recoveryError}</div>}
          {recoverySuccess && <div className="settings-success">{recoverySuccess}</div>}
        </div>

        {!isRecoveringPassword ? (
          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="auth-field">
              <span>Username</span>
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
              />
            </label>

            <label className="auth-field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={isSetup ? "new-password" : "current-password"}
              />
            </label>

            <button className="auth-button" type="submit" disabled={isSubmitting}>
              {isSetup ? "Create admin" : "Sign in"}
            </button>

            {!isSetup && (
              <button
                className="auth-link-button"
                type="button"
                onClick={() => {
                  setRecoveryError("");
                  setRecoverySuccess("");
                  setIsRecoveringPassword(true);
                }}
              >
                Forgot password?
              </button>
            )}
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleRecoverPassword}>
            <label className="auth-field">
              <span>Username</span>
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
              />
            </label>

            <label className="auth-field">
              <span>Recovery code</span>
              <input
                type="text"
                value={recoveryCode}
                onChange={(event) => setRecoveryCode(event.target.value)}
                autoComplete="one-time-code"
              />
            </label>

            <label className="auth-field">
              <span>New password</span>
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
              />
            </label>

            <label className="auth-field">
              <span>Confirm new password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
              />
            </label>

            <button className="auth-button" type="submit" disabled={isSubmitting}>
              Reset password
            </button>

            <button
              className="auth-link-button"
              type="button"
              onClick={() => {
                setIsRecoveringPassword(false);
                setRecoveryError("");
              }}
            >
              Back to sign in
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
