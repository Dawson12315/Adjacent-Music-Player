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
      "audio_analysis_enabled", "audio_analysis_time",
      "cleanup_enabled", "cleanup_time", "lastfm_api_key", "lastfm_api_secret",
      "lastfm_enrichment_enabled", "lastfm_enrichment_time", "lastfm_username",
      "lyrics_generation_enabled", "lyrics_model", "lyrics_time",
      "scan_enabled", "scan_time", "watch_enabled",
    ]);
    expect(saved.watch_enabled).toBe(true);
  });

  it("reads audio analysis as on with the default time, and carries a switch-off", async () => {
    expect(toAppSettings({}).audio_analysis_enabled).toBe(true);
    expect(toAppSettings({}).audio_analysis_time).toBe("03:30");
    expect(toAppSettings({ audio_analysis_enabled: false, audio_analysis_time: "04:15" })).toMatchObject({
      audio_analysis_enabled: false,
      audio_analysis_time: "04:15",
    });

    api.put.mockResolvedValueOnce({ audio_analysis_enabled: false });
    await saveSettings({ ...toAppSettings({}), audio_analysis_enabled: false, audio_analysis_time: "" });
    const [, payload] = api.put.mock.calls[0];
    expect(payload.audio_analysis_enabled).toBe(false);
    expect(payload.audio_analysis_time).toBeNull();
  });
});
