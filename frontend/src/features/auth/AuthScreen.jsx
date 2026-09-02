import { useState } from "react";

import { DuckMark } from "../../components/DuckMark";
import { useAuth } from "../../contexts/AuthContext";
import { recoverPassword } from "../../services/authService";

export function AuthScreen({ mode }) {
  const { login, setupAdmin, authError, sessionExpired, setupTokenRequired } = useAuth();

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [setupToken, setSetupToken] = useState("");
  const [isRecovering, setIsRecovering] = useState(false);
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
        await setupAdmin(username, password, setupToken);
      } else {
        await login(username, password);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRecover(event) {
    event.preventDefault();
    setRecoveryError("");
    setRecoverySuccess("");
    setIsSubmitting(true);

    try {
      await recoverPassword({ username, recoveryCode, newPassword, confirmPassword });

      setRecoverySuccess("Password reset. You can sign in now.");
      setPassword("");
      setRecoveryCode("");
      setNewPassword("");
      setConfirmPassword("");
      setIsRecovering(false);
    } catch (error) {
      setRecoveryError(error.message || "Could not reset your password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <DuckMark tile className="auth-mark" />
        <span className="auth-brand">Adjacent</span>

        <h1 className="auth-title">
          {isSetup ? "Create your account" : isRecovering ? "Reset password" : "Welcome back"}
        </h1>

        <p className="auth-subtitle">
          {isSetup
            ? "Set up the first admin account to secure your library."
            : isRecovering
            ? "Use one of your saved recovery codes."
            : "Sign in to get back to your music."}
        </p>

        <div aria-live="polite" style={{ width: "100%" }}>
          {sessionExpired && !isRecovering && (
            <div className="auth-error">Your session expired. Please sign in again.</div>
          )}
          {authError && !isRecovering && <div className="auth-error">{authError}</div>}
          {recoveryError && <div className="auth-error">{recoveryError}</div>}
          {recoverySuccess && <div className="settings-success">{recoverySuccess}</div>}
        </div>

        {!isRecovering ? (
          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="field">
              <span className="field__label">Username</span>
              <input
                className="input"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
              />
            </label>

            <label className="field">
              <span className="field__label">Password</span>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={isSetup ? "new-password" : "current-password"}
              />
            </label>

            {isSetup && setupTokenRequired && (
              <label className="field">
                <span className="field__label">Setup token</span>
                <input
                  className="input"
                  type="password"
                  value={setupToken}
                  onChange={(event) => setSetupToken(event.target.value)}
                  autoComplete="off"
                />
                <span className="field__hint">
                  This server requires the SETUP_TOKEN value from its
                  configuration to create the first account.
                </span>
              </label>
            )}

            <button className="btn btn--primary btn--lg btn--block" type="submit" disabled={isSubmitting}>
              {isSetup ? "Create account" : "Sign in"}
            </button>

            {!isSetup && (
              <button
                className="auth-link-button"
                type="button"
                onClick={() => {
                  setRecoveryError("");
                  setRecoverySuccess("");
                  setIsRecovering(true);
                }}
              >
                Forgot your password?
              </button>
            )}
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleRecover}>
            <label className="field">
              <span className="field__label">Username</span>
              <input
                className="input"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
              />
            </label>

            <label className="field">
              <span className="field__label">Recovery code</span>
              <input
                className="input"
                type="text"
                value={recoveryCode}
                onChange={(event) => setRecoveryCode(event.target.value)}
                autoComplete="one-time-code"
              />
            </label>

            <label className="field">
              <span className="field__label">New password</span>
              <input
                className="input"
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
              />
            </label>

            <label className="field">
              <span className="field__label">Confirm new password</span>
              <input
                className="input"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
              />
            </label>

            <button className="btn btn--primary btn--lg btn--block" type="submit" disabled={isSubmitting}>
              Reset password
            </button>

            <button
              className="auth-link-button"
              type="button"
              onClick={() => {
                setIsRecovering(false);
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
