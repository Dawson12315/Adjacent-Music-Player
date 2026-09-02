import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../../contexts/AuthContext";
import { useNotifications } from "../../contexts/NotificationContext";
import {
  createUser,
  listUsers,
  resetUserPassword,
  updateUser,
} from "../../services/usersService";

/**
 * The permanent management surface for a multi-user install: everyone who can
 * sign in, plus add / reset / deactivate / role changes. Rendered only when
 * multi-user is active and the viewer is an admin.
 *
 * Generated temp passwords are shown exactly once, in a dismissable card —
 * the API never returns them again.
 */
export function UsersPanel() {
  const { currentUser } = useAuth();
  const { notify } = useNotifications();

  const [users, setUsers] = useState(null);
  const [isAdding, setIsAdding] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [isSaving, setIsSaving] = useState(false);
  const [revealed, setRevealed] = useState(null); // {username, tempPassword, kind}

  const refresh = useCallback(() => {
    return listUsers()
      .then(setUsers)
      .catch(() => setUsers([]));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleCreate() {
    const username = newUsername.trim();

    if (username.length < 3) {
      notify("Usernames need at least 3 characters.");
      return;
    }

    setIsSaving(true);

    try {
      const created = await createUser({ username, role: newRole });
      setRevealed({
        username: created.user.username,
        tempPassword: created.temp_password,
        kind: "created",
      });
      setIsAdding(false);
      setNewUsername("");
      setNewRole("user");
      refresh();
    } catch (error) {
      notify(error.message || "Could not create the user.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReset(user) {
    try {
      const result = await resetUserPassword(user.id);
      setRevealed({
        username: user.username,
        tempPassword: result.temp_password,
        kind: "reset",
      });
    } catch (error) {
      notify(error.message || "Could not reset the password.");
    }
  }

  async function handleUpdate(user, changes) {
    try {
      await updateUser(user.id, changes);
      refresh();
    } catch (error) {
      notify(error.message || "Could not update the user.");
    }
  }

  function copyTempPassword() {
    navigator.clipboard
      ?.writeText(revealed.tempPassword)
      .then(() => notify("Temporary password copied."))
      .catch(() => notify("Copy failed — select and copy it by hand."));
  }

  if (!users) {
    return null;
  }

  return (
    <section className="settings-section">
      <div className="settings-section__header">
        <h2>Users</h2>
        <p>
          Everyone who can sign in to this install. Each user has their own
          playlists, likes, history and recommendations.
        </p>
      </div>

      {revealed && (
        <div className="settings-card users-reveal">
          <div className="settings-card__title">
            {revealed.kind === "created"
              ? `${revealed.username} was created`
              : `New password for ${revealed.username}`}
          </div>
          <div className="settings-card__text">
            Share this one-time password with them — it is shown{" "}
            <b>only once</b>. They'll be asked to set their own on first
            sign-in.
          </div>
          <div className="settings-card__actions">
            <span className="users-temp-password">🦆 {revealed.tempPassword}</span>
            <button className="btn" type="button" onClick={copyTempPassword}>
              Copy
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() => setRevealed(null)}
            >
              Done
            </button>
          </div>
        </div>
      )}

      <div className="settings-card">
        <div className="table-scroll">
          <table className="users-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const isSelf = user.id === currentUser?.id;

                return (
                  <tr key={user.id}>
                    <td>
                      <b>{user.username}</b>
                      {isSelf && <span className="users-self"> (you)</span>}
                    </td>
                    <td>
                      <span
                        className={`server-chip ${
                          user.role === "admin"
                            ? "server-chip--admin"
                            : "server-chip--busy"
                        }`}
                      >
                        {user.role}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`server-chip ${
                          user.is_active ? "server-chip--ok" : "server-chip--err"
                        }`}
                      >
                        {user.is_active ? "active" : "deactivated"}
                      </span>
                    </td>
                    <td className="users-created">
                      {user.created_at
                        ? new Date(user.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            year: "numeric",
                          })
                        : "—"}
                    </td>
                    <td className="users-actions">
                      {!isSelf && (
                        <>
                          <button
                            className="btn btn--sm"
                            type="button"
                            onClick={() => handleReset(user)}
                          >
                            Reset password
                          </button>
                          <button
                            className="btn btn--sm"
                            type="button"
                            onClick={() =>
                              handleUpdate(user, {
                                role: user.role === "admin" ? "user" : "admin",
                              })
                            }
                          >
                            {user.role === "admin" ? "Make user" : "Make admin"}
                          </button>
                          <button
                            className="btn btn--sm btn--danger"
                            type="button"
                            onClick={() =>
                              handleUpdate(user, { is_active: !user.is_active })
                            }
                          >
                            {user.is_active ? "Deactivate" : "Reactivate"}
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {isAdding ? (
          <div className="users-add-form">
            <label className="field">
              <span className="field__label">Username</span>
              <input
                className="input"
                type="text"
                value={newUsername}
                onChange={(event) => setNewUsername(event.target.value)}
                autoFocus
              />
            </label>
            <label className="field">
              <span className="field__label">Role</span>
              <select
                className="input"
                value={newRole}
                onChange={(event) => setNewRole(event.target.value)}
              >
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </label>
            <div className="settings-card__actions">
              <button
                className="btn"
                type="button"
                onClick={() => setIsAdding(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn--primary"
                type="button"
                onClick={handleCreate}
                disabled={isSaving}
              >
                {isSaving ? "Creating…" : "Create user"}
              </button>
            </div>
          </div>
        ) : (
          <div className="settings-card__actions">
            <button
              className="btn btn--primary"
              type="button"
              onClick={() => setIsAdding(true)}
            >
              + Add user
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
