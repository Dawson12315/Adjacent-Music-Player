import { useEffect, useState } from "react";

import { useAuth } from "../../contexts/AuthContext";
import { useTransientMessage } from "../../hooks/useTransientMessage";
import { generateRecoveryCodes } from "../../services/authService";
import { getRadioTaste, resetRadioTaste } from "../../services/radioService";
import { browserTimeZone, timeZoneChoices, zoneLabel } from "../../utils/timezone";

export function AccountPanel() {
  const { currentUser, updateAccount, updatePreferences, logout } = useAuth();

  // Insights count days and hours in this zone. Empty means "follow this
  // browser", which is what a fresh account gets.
  const browserZone = browserTimeZone();
  const [timezoneSaving, setTimezoneSaving] = useState(false);
  const [timezoneError, setTimezoneError] = useTransientMessage();
  const zoneChoices = timeZoneChoices();

  async function handleTimezoneChange(event) {
    const chosen = event.target.value || null;
    setTimezoneError("");
    setTimezoneSaving(true);

    try {
      await updatePreferences({ timezone: chosen });
    } catch (saveError) {
      setTimezoneError(saveError.message || "Could not save the time zone.");
    } finally {
      setTimezoneSaving(false);
    }
  }

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

        <div className="account-grid">
          <label className="field">
            <span className="field__label">Username</span>
            <input
              className="input"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Username"
              autoComplete="username"
            />
          </label>

          <label className="field">
            <span className="field__label">Current password</span>
            <input
              className="input"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              placeholder="Required"
              autoComplete="current-password"
            />
          </label>

          <label className="field">
            <span className="field__label">New password</span>
            <input
              className="input"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              placeholder="Leave blank to keep current password"
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
              placeholder="Repeat new password"
              autoComplete="new-password"
            />
          </label>
        </div>

        <div className="settings-card__actions">
          <button
            className="btn btn--primary"
            type="button"
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? "Saving..." : "Save account"}
          </button>

          <button className="btn btn--danger" type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-card__title">Time zone</div>
        <div className="settings-card__text">
          Insights count your days, streaks and listening hours in this zone.
          Left on this browser's, it follows wherever you sign in from.
        </div>

        <div aria-live="polite">
          {timezoneError && <div className="settings-error">{timezoneError}</div>}
        </div>

        <label className="field">
          <span className="field__label">Count my days in</span>
          <select
            className="input"
            value={currentUser?.timezone || ""}
            onChange={handleTimezoneChange}
            disabled={timezoneSaving}
          >
            <option value="">
              {browserZone ? `This browser's time zone (${zoneLabel(browserZone)})` : "This browser's time zone"}
            </option>
            {zoneChoices.map((zone) => (
              <option key={zone} value={zone}>
                {zoneLabel(zone)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="settings-card">
        <div className="settings-card__title">Password Recovery Codes</div>

        <div className="settings-card__text">
          Generate one-time recovery codes you can use if you forget your password. Save
          them somewhere safe. Existing recovery codes will be replaced.
        </div>

        <div className="settings-card__actions">
          <button
            className="btn"
            type="button"
            onClick={handleGenerateRecoveryCodes}
            disabled={isGenerating}
          >
            {isGenerating ? "Generating..." : "Generate recovery codes"}
          </button>
        </div>

        {recoveryError && <div className="settings-error">{recoveryError}</div>}

        {recoveryCodes.length > 0 && (
          <div className="recovery-codes">
            {recoveryCodes.map((code) => (
              <code key={code} className="recovery-code">
                {code}
              </code>
            ))}
          </div>
        )}
      </div>

      <RadioTasteCard />
    </section>
  );
}

/**
 * What the thumbs on radio stations leave behind. Each vote nudges where
 * this account keeps the artist on the server's map, so stations started
 * later lean the same way; this says how much has built up and lets the
 * listener wipe it. Hidden on a server that has no map.
 */
export function RadioTasteCard() {
  const [taste, setTaste] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useTransientMessage();

  useEffect(() => {
    let cancelled = false;
    getRadioTaste()
      .then((answer) => {
        if (!cancelled) setTaste(answer);
      })
      .catch(() => {
        if (!cancelled) setTaste(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!taste) return null;

  const votes = (taste.votes_up || 0) + (taste.votes_down || 0);
  const artists = taste.artists || 0;
  const line =
    artists === 0
      ? "Nothing yet. Thumbs on a station nudge where this account keeps an artist, so the stations you start next lean the same way."
      : `${votes} ${votes === 1 ? "vote" : "votes"} have nudged ${artists} ${artists === 1 ? "artist" : "artists"}. Stations you start next lean the same way; it fades over a few months.`;

  async function handleReset() {
    setError("");
    setResetting(true);
    try {
      const cleared = await resetRadioTaste();
      setTaste({ ...cleared, cleared: undefined });
    } catch (resetError) {
      setError(resetError.message || "Could not reset your radio taste.");
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="settings-card" data-testid="radio-taste">
      <div className="settings-card__title">Radio taste</div>
      <div className="settings-card__text">{line}</div>
      {error && <div className="settings-error">{error}</div>}
      <div className="settings-card__actions">
        <button className="btn" type="button" onClick={handleReset} disabled={resetting || artists === 0}>
          {resetting ? "Resetting…" : "Reset radio taste"}
        </button>
      </div>
    </div>
  );
}
