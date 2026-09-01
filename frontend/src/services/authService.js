import { apiClient } from "./apiClient";

/**
 * Auth is cookie-based end to end: the backend sets an httpOnly `adjacent_access_token`
 * cookie and every request carries `credentials: "include"`. The frontend never holds a
 * token, which is why there is nothing here that reads or stores one.
 */

export function getSetupStatus() {
  return apiClient.get("/api/auth/setup-status");
}

/** `GET /api/auth/me` returns a bare user object, unlike login/setup which wrap it. */
export function getCurrentUser() {
  return apiClient.get("/api/auth/me", { suppressUnauthorized: true });
}

export async function setupAdmin(username, password) {
  const data = await apiClient.post("/api/auth/setup-admin", { username, password });
  return data.user;
}

export async function login(username, password) {
  // A 401 here means "wrong password", not "session expired", so it must not trigger
  // the global unauthorized signal.
  const data = await apiClient.post(
    "/api/auth/login",
    { username, password },
    { suppressUnauthorized: true },
  );

  return data.user;
}

export function logout() {
  return apiClient.post("/api/auth/logout");
}

export async function updateAccount({
  username,
  currentPassword,
  newPassword,
  confirmPassword,
}) {
  const data = await apiClient.patch("/api/auth/me", {
    username,
    current_password: currentPassword,
    new_password: newPassword || null,
    confirm_password: confirmPassword || null,
  });

  return data.user;
}

export async function generateRecoveryCodes() {
  const data = await apiClient.post("/api/auth/recovery-codes");
  return data.recovery_codes || [];
}

/** Does not sign the user in — they must log in with the new password afterwards. */
export function recoverPassword({
  username,
  recoveryCode,
  newPassword,
  confirmPassword,
}) {
  return apiClient.post(
    "/api/auth/recover-password",
    {
      username,
      recovery_code: recoveryCode,
      new_password: newPassword,
      confirm_password: confirmPassword,
    },
    { suppressUnauthorized: true },
  );
}
