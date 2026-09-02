import { useCallback, useEffect, useState } from "react";

import { Modal } from "../../components/Modal";
import { UsersPanel } from "./UsersPanel";
import { useAuth } from "../../contexts/AuthContext";
import { useNotifications } from "../../contexts/NotificationContext";
import {
  getDatabaseMigrationProgress,
  getDatabaseStatus,
  pingHealth,
  startDatabaseMigration,
  testDatabaseConnection,
} from "../../services/settingsService";

const EMPTY_FORM = {
  host: "",
  port: "5432",
  database: "adjacent",
  username: "adjacent",
  password: "",
  sslmode: "prefer",
};

const MIGRATION_STEPS = [
  { key: "snapshot", label: "Snapshot", detail: "consistent copy of SQLite taken" },
  { key: "schema", label: "Schema", detail: "tables created on PostgreSQL" },
  { key: "copy", label: "Data", detail: "rows copied in batches" },
  { key: "verify", label: "Verify", detail: "row counts & checksums" },
  { key: "cutover", label: "Cut over", detail: "config written, restart" },
];

// How long to wait for the server to come back after cutover before telling
// the user to restart it by hand (bare-metal installs have no supervisor).
const RECONNECT_TIMEOUT_MS = 60_000;

function formatBytes(bytes) {
  if (bytes == null) return null;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * The Server section: multi-user support, the Postgres connection form, the
 * migration itself, and afterwards the "this install runs on PostgreSQL"
 * status. Admin-only — everyone else sees Settings exactly as before.
 */
export function ServerPanel() {
  const { currentUser } = useAuth();
  const { notify } = useNotifications();

  const [status, setStatus] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testedFingerprint, setTestedFingerprint] = useState(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [confirmWord, setConfirmWord] = useState("");
  const [migration, setMigration] = useState(null);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [needsManualRestart, setNeedsManualRestart] = useState(false);

  const isAdmin = currentUser?.role === "admin";

  const refreshStatus = useCallback(() => {
    return getDatabaseStatus()
      .then((data) => {
        setStatus(data);
        if (["running", "restarting"].includes(data.migration?.state)) {
          setMigration(data.migration);
        }
        return data;
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    refreshStatus();
  }, [isAdmin, refreshStatus]);

  // Poll the running migration once a second. When the poll reports
  // "restarting" — or stops answering because the process exited — switch to
  // waiting for the server to come back.
  const migrationState = migration?.state;

  useEffect(() => {
    if (migrationState !== "running") {
      return undefined;
    }

    const timer = setInterval(() => {
      getDatabaseMigrationProgress()
        .then((progress) => {
          setMigration(progress);
          if (progress.state === "restarting") {
            setIsReconnecting(true);
          }
        })
        .catch(() => {
          setIsReconnecting(true);
        });
    }, 1000);

    return () => clearInterval(timer);
  }, [migrationState]);

  useEffect(() => {
    if (!isReconnecting) {
      return undefined;
    }

    const startedAt = Date.now();
    const timer = setInterval(() => {
      pingHealth()
        .then(() => {
          clearInterval(timer);
          setIsReconnecting(false);
          setMigration(null);
          refreshStatus().then((data) => {
            if (data?.engine === "postgresql") {
              notify("Migration complete — Adjacent now runs on PostgreSQL.");
            }
          });
        })
        .catch(() => {
          if (Date.now() - startedAt > RECONNECT_TIMEOUT_MS) {
            clearInterval(timer);
            setNeedsManualRestart(true);
          }
        });
    }, 2000);

    return () => clearInterval(timer);
  }, [isReconnecting, refreshStatus, notify]);

  // A successful test is only valid for the exact fields it tested.
  const fingerprint = JSON.stringify(form);
  const isTestCurrent = testResult?.ok && testedFingerprint === fingerprint;

  function updateField(field) {
    return (event) => {
      setForm((previous) => ({ ...previous, [field]: event.target.value }));
    };
  }

  function connectionPayload() {
    return {
      host: form.host.trim(),
      port: Number(form.port) || 5432,
      database: form.database.trim(),
      username: form.username.trim(),
      password: form.password,
      sslmode: form.sslmode,
    };
  }

  async function handleTest() {
    if (!form.host.trim() || !form.database.trim() || !form.username.trim()) {
      notify("Host, database and username are required.");
      return;
    }

    setIsTesting(true);
    setTestResult(null);

    try {
      const result = await testDatabaseConnection(connectionPayload());
      setTestResult(result);
      setTestedFingerprint(fingerprint);
    } catch (error) {
      setTestResult({ ok: false, error: error.message || "Connection failed." });
      setTestedFingerprint(null);
    } finally {
      setIsTesting(false);
    }
  }

  async function handleConfirmMigrate() {
    setIsConfirming(false);
    setConfirmWord("");

    try {
      await startDatabaseMigration(connectionPayload());
      setMigration({ state: "running", step: "snapshot", rows_done: 0, rows_total: 0 });
    } catch (error) {
      notify(error.message || "Failed to start the migration.");
    }
  }

  if (!isAdmin || !status) {
    return null;
  }

  const rowCountLabel = status.row_count?.toLocaleString?.() || status.row_count;

  return (
    <>
    <section className="settings-section">
      <div className="settings-section__header">
        <h2>Server</h2>
        <p>How this Adjacent install stores its data and who can sign in.</p>
      </div>

      {status.engine === "postgresql" ? (
        <div className="settings-card">
          <div className="settings-card__title server-card__title-row">
            <span>Multi-user support</span>
            <span className="server-chip server-chip--ok">
              Active · PostgreSQL
            </span>
          </div>
          <div className="settings-card__text">
            This install is multi-user. The catalog, playlists and listening
            history live on <code>{status.url_masked}</code>.
            {status.migrated_at &&
              ` Migrated ${new Date(status.migrated_at).toLocaleDateString()}.`}{" "}
            The old SQLite file was kept as a backup in the data directory.
          </div>
        </div>
      ) : migration && ["running", "restarting"].includes(migration.state) ? (
        <MigrationProgressCard
          migration={migration}
          isReconnecting={isReconnecting}
          needsManualRestart={needsManualRestart}
        />
      ) : migration?.state === "failed" ? (
        <div className="settings-card settings-card--danger">
          <div className="settings-card__title server-card__title-row">
            <span>Migration failed — nothing was lost</span>
            <span className="server-chip server-chip--err">Failed</span>
          </div>
          <div className="settings-card__text">
            {migration.error || "The migration stopped."} Adjacent is still
            running normally on SQLite — nothing changed. The partial copy on
            PostgreSQL was wiped, so the next attempt starts clean.
          </div>
          <div className="settings-card__actions">
            <button
              className="btn btn--primary"
              type="button"
              onClick={() => {
                setMigration(null);
                setTestResult(null);
                setTestedFingerprint(null);
              }}
            >
              Back to the form
            </button>
          </div>
        </div>
      ) : (
        <div className="settings-card">
          <div className="settings-card__title server-card__title-row">
            <span>Multi-user support</span>
            <button
              className={`switch ${isExpanded ? "switch--on" : ""}`}
              type="button"
              role="switch"
              aria-checked={isExpanded}
              aria-label="Enable multi-user support"
              onClick={() => setIsExpanded((open) => !open)}
            >
              <span className="switch__knob" />
            </button>
          </div>

          {!isExpanded ? (
            <>
              <div className="settings-card__text">
                Adjacent is running in single-user mode on SQLite — zero-setup,
                perfect for one person. Turning this on connects a PostgreSQL
                database and unlocks additional accounts, each with their own
                playlists, likes, listening history and recommendations. The
                music library itself stays shared.
              </div>
              <div className="settings-card__text server-engine-line">
                Engine: <code>SQLite</code>
                {status.size_bytes != null && ` · ${formatBytes(status.size_bytes)}`}
                {` · ${rowCountLabel} rows`}
              </div>
            </>
          ) : (
            <>
              <div className="settings-card__text">
                Connect the PostgreSQL database this install should migrate to.
                Your music files are not touched — only the catalog, playlists
                and listening history move.
              </div>

              <div className="server-form-grid">
                <label className="field">
                  <span className="field__label">Host</span>
                  <input
                    className="input"
                    type="text"
                    value={form.host}
                    placeholder="postgres"
                    onChange={updateField("host")}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Port</span>
                  <input
                    className="input"
                    type="text"
                    inputMode="numeric"
                    value={form.port}
                    onChange={updateField("port")}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Database</span>
                  <input
                    className="input"
                    type="text"
                    value={form.database}
                    onChange={updateField("database")}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Username</span>
                  <input
                    className="input"
                    type="text"
                    value={form.username}
                    onChange={updateField("username")}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Password</span>
                  <input
                    className="input"
                    type="password"
                    value={form.password}
                    onChange={updateField("password")}
                  />
                </label>
                <label className="field">
                  <span className="field__label">SSL</span>
                  <select
                    className="input"
                    value={form.sslmode}
                    onChange={updateField("sslmode")}
                  >
                    <option value="prefer">prefer (try TLS, fall back)</option>
                    <option value="disable">disable (local network)</option>
                    <option value="require">require</option>
                  </select>
                </label>
              </div>

              {testResult && !isTestCurrent && !testResult.ok && (
                <div className="settings-error">✕ {testResult.error}</div>
              )}
              {isTestCurrent && (
                <div className="settings-success">
                  ✓ Connected — PostgreSQL {testResult.server_version}
                  {testResult.target_state === "empty" &&
                    `, database “${form.database}” is empty and ready`}
                  {testResult.target_state === "leftover_adjacent" &&
                    " — a previous attempt's leftovers will be cleared"}
                </div>
              )}

              <div className="settings-card__actions">
                <button
                  className="btn"
                  type="button"
                  onClick={handleTest}
                  disabled={isTesting}
                >
                  {isTesting ? "Testing…" : "Test connection"}
                </button>
                <button
                  className="btn btn--primary"
                  type="button"
                  disabled={!isTestCurrent}
                  onClick={() => setIsConfirming(true)}
                >
                  Migrate &amp; enable
                </button>
              </div>

              <div className="settings-card__text server-help-line">
                Don't have Postgres yet? A ready-made docker compose service is
                in the README — one block to paste, then come back here.
              </div>
            </>
          )}
        </div>
      )}

      {isConfirming && (
        <Modal
          title="Migrate to PostgreSQL?"
          onClose={() => {
            setIsConfirming(false);
            setConfirmWord("");
          }}
          actions={
            <>
              <button
                className="btn"
                type="button"
                onClick={() => {
                  setIsConfirming(false);
                  setConfirmWord("");
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn--primary"
                type="button"
                disabled={confirmWord.trim().toLowerCase() !== "migrate"}
                onClick={handleConfirmMigrate}
              >
                Yes, migrate
              </button>
            </>
          }
        >
          <p className="settings-card__text">Here is exactly what will happen:</p>
          <ul className="server-modal-list">
            <li>
              Adjacent goes <b>read-only for about a minute</b> — playback keeps
              working, edits are paused.
            </li>
            <li>
              All {status.table_count} tables ({rowCountLabel} rows
              {status.size_bytes != null && `, ${formatBytes(status.size_bytes)}`}
              ) are copied to{" "}
              <code>
                {form.host}:{form.port}/{form.database}
              </code>{" "}
              and verified row-for-row.
            </li>
            <li>The server restarts on the new database. You stay signed in.</li>
            <li>
              Your SQLite file is kept untouched as a backup in the data
              directory.
            </li>
          </ul>
          <p className="settings-card__text server-modal-warning">
            This is a one-way switch — there is no “migrate back” button.
            Returning to SQLite would be a manual restore from the backup.
          </p>
          <label className="field">
            <span className="field__label">
              Type <b>migrate</b> to confirm
            </span>
            <input
              className="input"
              type="text"
              value={confirmWord}
              placeholder="migrate"
              onChange={(event) => setConfirmWord(event.target.value)}
            />
          </label>
        </Modal>
      )}
    </section>

    {status.engine === "postgresql" && <UsersPanel />}
    </>
  );
}

function MigrationProgressCard({ migration, isReconnecting, needsManualRestart }) {
  const stepIndex = MIGRATION_STEPS.findIndex((step) => step.key === migration.step);
  const isRestartPhase = migration.state === "restarting" || isReconnecting;

  const percent = migration.rows_total
    ? Math.round((migration.rows_done / migration.rows_total) * 100)
    : 0;

  return (
    <>
      <div className="server-banner">
        ⏸ Maintenance — Adjacent is read-only while the database migrates.
        Playback continues; edits resume shortly.
      </div>

      <div className="settings-card">
        <div className="settings-card__title server-card__title-row">
          <span>Migrating to PostgreSQL</span>
          <span className="server-chip server-chip--busy">
            {needsManualRestart
              ? "Waiting for restart"
              : isRestartPhase
              ? "Restarting server…"
              : "Running"}
          </span>
        </div>

        <ol className="server-steps">
          {MIGRATION_STEPS.map((step, index) => {
            const state = isRestartPhase
              ? index < MIGRATION_STEPS.length - 1
                ? "done"
                : "run"
              : index < stepIndex
              ? "done"
              : index === stepIndex
              ? "run"
              : "wait";

            return (
              <li key={step.key} className={`server-step server-step--${state}`}>
                <span className="server-step__status">
                  {state === "done" ? "DONE" : state === "run" ? "…" : "WAITING"}
                </span>
                <span>
                  {step.label}
                  {step.key === "copy" && state === "run" && migration.table
                    ? ` — ${migration.table}`
                    : ` — ${step.detail}`}
                </span>
              </li>
            );
          })}
        </ol>

        {!isRestartPhase && migration.rows_total > 0 && (
          <div className="server-progress">
            <div className="server-progress__label">
              <span>
                {migration.rows_done?.toLocaleString()} /{" "}
                {migration.rows_total?.toLocaleString()} rows
              </span>
              <span>{percent}%</span>
            </div>
            <div className="server-progress__bar">
              <div
                className="server-progress__fill"
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>
        )}

        {needsManualRestart ? (
          <div className="settings-error">
            The migration finished and the config is written, but the server
            has not come back on its own. Restart it manually to finish — it
            will boot on PostgreSQL.
          </div>
        ) : (
          isRestartPhase && (
            <div className="settings-card__text">
              This takes a few seconds in Docker. You'll stay signed in.
            </div>
          )
        )}
      </div>
    </>
  );
}
