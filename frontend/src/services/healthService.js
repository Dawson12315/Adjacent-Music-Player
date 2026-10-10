/**
 * The server's health, read for its capability list. Device handoff turns on
 * only when the server advertises it, so the browser asks once after sign-in.
 */

import { apiClient } from "./apiClient";

export async function getHealth(options) {
  const data = await apiClient.get("/api/health", options);
  return {
    apiVersion: Number.isFinite(Number(data?.api_version)) ? Number(data.api_version) : 0,
    capabilities: Array.isArray(data?.capabilities) ? data.capabilities : [],
    sessionDays: Number.isFinite(Number(data?.session_days)) ? Number(data.session_days) : null,
  };
}
