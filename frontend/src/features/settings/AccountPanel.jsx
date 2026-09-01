import { useEffect, useState } from "react";

import { useAuth } from "../../contexts/AuthContext";
import { useTransientMessage } from "../../hooks/useTransientMessage";
import { generateRecoveryCodes } from "../../services/authService";

export function AccountPanel() {
  const { currentUser, updateAccount, logout } = useAuth();

  const [username, setUsername] = useState(currentUser?.username || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const [error, setError] = useTransientMessage();
  const [success, setSuccess] = useTransientMessage();

  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [recoveryError, setRecoveryError] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (currentUser?.username) {
      setUsername(currentUser.username);
    }
  }, [currentUser?.username]);

  async function handleSave() {
    setError("");
    setSuccess("");

    if (!currentPassword) {
      setError("Enter your current password to make account changes.");
      return;
    }

    if ((newPassword || confirmPassword) && newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setIsSaving(true);

    try {
      const user = await updateAccount({
        username: username.trim() || currentUser.username,
        currentPassword,
        newPassword,
        confirmPassword,
      });

      setUsername(user.username);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess("Account updated successfully.");
    } catch (saveError) {
      setError(saveError.message || "Failed to update account.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGenerateRecoveryCodes() {
    setRecoveryError("");
    setRecoveryCodes([]);
    setIsGenerating(true);

    try {
      setRecoveryCodes(await generateRecoveryCodes());
    } catch (codesError) {
      setRecoveryError(codesError.message || "Failed to generate recovery codes.");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <section className="settings-section">
      <div className="settings-section__header">
        <h2>Account</h2>
        <p>Manage your local Adjacent account.</p>
      </div>

      <div className="settings-card">
        <div className="settings-card__title">Account credentials</div>
        <div className="settings-card__text">
          Update your username or password. Your current password is required for any
          account change.
        </div>

        <div aria-live="polite">
          {error && <div className="settings-error">{error}</div>}
          {success && <div className="settings-success">{success}</div>}
        </div>

        <div className="account-settings-grid">
          <label className="settings-field">
            <span className="settings-field__label">Username</span>
            <input
              className="settings-text-input"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Username"
              autoComplete="username"
            />
          </label>

          <label className="settings-field">
            <span className="settings-field__label">Current password</span>
            <input
              className="settings-text-input"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              placeholder="Required"
              autoComplete="current-password"
            />
          </label>

          <label className="settings-field">
            <span className="settings-field__label">New password</span>
            <input
              className="settings-text-input"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              placeholder="Leave blank to keep current password"
              autoComplete="new-password"
            />
          </label>

          <label className="settings-field">
            <span className="settings-field__label">Confirm new password</span>
            <input
              className="settings-text-input"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Repeat new password"
              autoComplete="new-password"
            />
          </label>
        </div>

        <div className="settings-card__actions">
          <button
            className="settings-button"
            type="button"
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? "Saving..." : "Save account"}
          </button>

          <button className="logout-button" type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-card__title">Password Recovery Codes</div>

        <div className="settings-card__text">
          Generate one-time recovery codes you can use if you forget your password. Save
          them somewhere safe. Existing recovery codes will be replaced.
        </div>

        <div className="settings-card__actions">
          <button
            className="settings-button settings-button--secondary"
            type="button"
            onClick={handleGenerateRecoveryCodes}
            disabled={isGenerating}
          >
            {isGenerating ? "Generating..." : "Generate recovery codes"}
          </button>
        </div>

        {recoveryError && <div className="settings-error">{recoveryError}</div>}

        {recoveryCodes.length > 0 && (
          <div className="recovery-codes-box">
            {recoveryCodes.map((code) => (
              <code key={code} className="recovery-code">
                {code}
              </code>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
