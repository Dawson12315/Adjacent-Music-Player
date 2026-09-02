import { useState } from "react";

import { DuckMark } from "../../components/DuckMark";
import { useAuth } from "../../contexts/AuthContext";

/**
 * Shown instead of the app while the account carries a temp password an admin
 * handed out. The temp password is the "current" one; choosing a real
 * password clears the hold server-side and the gate lifts on its own.
 */
export function SetPasswordScreen() {
  const { currentUser, updateAccount, logout } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (newPassword.length < 8) {
      setError("The new password needs at least 8 characters.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await updateAccount({
        currentPassword,
        newPassword,
        confirmPassword,
      });
    } catch (submitError) {
      setError(submitError.message || "Could not set the password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <DuckMark tile className="auth-mark" />
        <span className="auth-brand">Adjacent</span>

        <h1 className="auth-title">Choose your password</h1>
        <p className="auth-subtitle">
          Welcome, {currentUser?.username}. The password you signed in with was
          a one-time password — pick your own to continue.
        </p>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="field">
            <span className="field__label">Temporary password</span>
            <input
              className="input"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              required
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
              required
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
              required
            />
          </label>

          <button className="btn btn--primary" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Set password"}
          </button>

          <button className="btn btn--ghost" type="button" onClick={logout}>
            Sign out
          </button>
        </form>
      </div>
    </div>
  );
}
