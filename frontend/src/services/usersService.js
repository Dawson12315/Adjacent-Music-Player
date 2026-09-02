import { apiClient } from "./apiClient";

/**
 * Admin user management. Only available when the install is multi-user
 * (running on Postgres) — on SQLite the API answers 403 and the UI never
 * shows these surfaces in the first place.
 */

export function listUsers(options) {
  return apiClient.get("/api/users", { ...options, noStore: true });
}

export function createUser({ username, role }) {
  return apiClient.post("/api/users", { username, role });
}

export function updateUser(userId, changes) {
  return apiClient.patch(`/api/users/${userId}`, changes);
}

export function resetUserPassword(userId) {
  return apiClient.post(`/api/users/${userId}/reset-password`);
}
