import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("./apiClient", () => ({ apiClient: { get: (...a) => get(...a) } }));
vi.mock("./normalize", () => ({ normalizeTracks: (data) => data, normalizeTrack: (t) => t }));

import { getTracksByIds } from "./tracksService";

describe("getTracksByIds", () => {
  beforeEach(() => get.mockReset());

  it("fetches a long list in pages of five hundred and returns all of it in order", async () => {
    get.mockImplementation((_url, opts) =>
      Promise.resolve(String(opts?.params?.ids ?? "").split(",").filter(Boolean).map((id) => ({ id: Number(id) }))),
    );
    const ids = Array.from({ length: 1203 }, (_, i) => i + 1);
    const tracks = await getTracksByIds(ids);
    expect(get).toHaveBeenCalledTimes(3);
    expect(tracks).toHaveLength(1203);
    expect(tracks[0].id).toBe(1);
    expect(tracks[1202].id).toBe(1203);
  });

  it("asks nothing for an empty list", async () => {
    expect(await getTracksByIds([])).toEqual([]);
    expect(get).not.toHaveBeenCalled();
  });
});
