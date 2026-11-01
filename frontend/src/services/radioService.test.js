import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

vi.mock("./apiClient", () => ({ apiClient: api }));
vi.mock("./normalize", () => ({ normalizeTrack: (track) => ({ ...track, normalized: true }) }));

import {
  deleteStation,
  getStationLineup,
  getStationNext,
  giveStationFeedback,
  reportStationPlays,
  takeBackStationFeedback,
} from "./radioService";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("the station's next batch", () => {
  it("sends what the browser holds, and reads thin and reach", async () => {
    api.get.mockResolvedValueOnce({
      station: { id: 4 },
      tracks: [{ id: 1, reason: "Close to Fen" }, { id: 2 }],
      thin: true,
      reach: "listener",
    });
    const batch = await getStationNext(4, { excludeIds: [7, null, 8] });
    expect(api.get).toHaveBeenCalledWith("/api/radio/stations/4/next", {
      params: { limit: 20, exclude_track_ids: "7,8" },
      signal: undefined,
    });
    expect(batch.tracks).toEqual([
      { id: 1, reason: "Close to Fen", normalized: true },
      { id: 2, reason: null, normalized: true },
    ]);
    expect(batch.thin).toBe(true);
    expect(batch.reach).toBe("listener");
  });

  it("leaves the exclude list off when there is nothing to exclude, and reads an empty answer", async () => {
    api.get.mockResolvedValueOnce({});
    const batch = await getStationNext(4);
    expect(api.get.mock.calls[0][1].params).toEqual({ limit: 20 });
    expect(batch).toEqual({ station: null, tracks: [], thin: false, reach: null });
  });
});

describe("the lineup", () => {
  it("keeps when it was saved", async () => {
    api.get.mockResolvedValueOnce({ station: { id: 4 }, tracks: [{ id: 9 }], resumable: true, saved_at: "2026-11-01T10:00:00" });
    const lineup = await getStationLineup(4);
    expect(lineup.resumable).toBe(true);
    expect(lineup.savedAt).toBe("2026-11-01T10:00:00");
    expect(lineup.tracks[0].id).toBe(9);
  });
});

describe("plays and feedback", () => {
  it("reports plays without blanks", () => {
    reportStationPlays(4, [1, null, 2]);
    expect(api.post).toHaveBeenCalledWith("/api/radio/stations/4/played", { track_ids: [1, 2] });
  });

  it("says more, less, less of an artist, and takes it back", () => {
    giveStationFeedback(4, 9, "less_artist");
    expect(api.post).toHaveBeenCalledWith("/api/radio/stations/4/feedback", { track_id: 9, kind: "less_artist" });
    takeBackStationFeedback(4, 9, "more");
    expect(api.delete).toHaveBeenCalledWith("/api/radio/stations/4/feedback", { params: { track_id: 9, kind: "more" } });
    deleteStation(4);
    expect(api.delete).toHaveBeenCalledWith("/api/radio/stations/4");
  });
});
