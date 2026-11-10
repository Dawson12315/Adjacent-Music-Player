import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock("./apiClient", () => ({ apiClient: api }));

import { currentLineIndex, describeLyricsSource, getLyrics, saveLyrics } from "./lyricsService";

beforeEach(() => vi.clearAllMocks());

describe("lyrics from the server", () => {
  it("reads timed lyrics into numbers, and a 404 into 'none' with the generation status", async () => {
    api.get.mockResolvedValueOnce({
      track_id: 7,
      source: "embedded",
      synced_source: "aligned",
      plain: "a\nb",
      synced: [{ t: "1.5", line: "a" }, { t: 4, line: "b" }],
      generated: true,
      model: "base",
    });
    const lyrics = await getLyrics(7);
    expect(lyrics.synced).toEqual([{ t: 1.5, line: "a" }, { t: 4, line: "b" }]);
    expect(describeLyricsSource(lyrics)).toBe("From the file · timed on your server");

    const error = Object.assign(new Error("not found"), { status: 404, detail: { code: "no_lyrics", generation: { state: "off" } } });
    api.get.mockRejectedValueOnce(error);
    expect(await getLyrics(8)).toEqual({ none: true, generation: { state: "off" } });

    api.get.mockRejectedValueOnce(Object.assign(new Error("boom"), { status: 500 }));
    await expect(getLyrics(9)).rejects.toThrow("boom");
  });

  it("names where the words came from", () => {
    expect(describeLyricsSource({ source: "transcribed", model: "small" })).toBe("Generated on your server (small) · may contain errors");
    expect(describeLyricsSource({ source: "user" })).toBe("Edited in Adjacent");
    expect(describeLyricsSource({ source: "sidecar" })).toBe("From a lyrics file beside the track");
    expect(describeLyricsSource({ none: true })).toBe("");
  });

  it("sends a correction with its timing, clamped and numeric", async () => {
    api.put.mockResolvedValueOnce({ track_id: 7, source: "user", plain: "a\nb", synced: [{ t: 0, line: "a" }] });
    await saveLyrics(7, { plain: "a\nb", synced: [{ t: -2, line: "a" }, { t: "3.25", line: "b" }] });
    expect(api.put).toHaveBeenCalledWith("/api/tracks/7/lyrics", {
      plain: "a\nb",
      synced: [{ t: 0, line: "a" }, { t: 3.25, line: "b" }],
    });
  });

  it("finds the line being sung", () => {
    const synced = [{ t: 1, line: "a" }, { t: 5, line: "b" }, { t: 9, line: "c" }];
    expect(currentLineIndex(synced, 0.5)).toBe(-1);
    expect(currentLineIndex(synced, 1)).toBe(0);
    expect(currentLineIndex(synced, 6.2)).toBe(1);
    expect(currentLineIndex(synced, 40)).toBe(2);
    expect(currentLineIndex(null, 3)).toBe(-1);
  });
});
