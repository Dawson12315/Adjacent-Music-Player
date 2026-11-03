import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock("./apiClient", () => ({ apiClient: api }));

import { saveSettings, toAppSettings } from "./settingsService";

beforeEach(() => vi.clearAllMocks());

describe("the app settings round trip", () => {
  it("carries the folder watch flag both ways, and reads it as off when absent", async () => {
    expect(toAppSettings({}).watch_enabled).toBe(false);
    expect(toAppSettings({ watch_enabled: true }).watch_enabled).toBe(true);

    api.put.mockResolvedValueOnce({ scan_enabled: true, watch_enabled: true });
    const saved = await saveSettings({ ...toAppSettings({}), scan_enabled: true, watch_enabled: true });

    const [path, payload] = api.put.mock.calls[0];
    expect(path).toBe("/api/settings");
    expect(payload.watch_enabled).toBe(true);
    expect(payload.scan_enabled).toBe(true);
    // Every field goes, so a save never drops one into null by omission.
    expect(Object.keys(payload).sort()).toEqual([
      "cleanup_enabled", "cleanup_time", "lastfm_api_key", "lastfm_api_secret",
      "lastfm_enrichment_enabled", "lastfm_enrichment_time", "lastfm_username",
      "scan_enabled", "scan_time", "watch_enabled",
    ]);
    expect(saved.watch_enabled).toBe(true);
  });
});
