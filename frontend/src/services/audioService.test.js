import { describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }));
vi.mock("./apiClient", () => ({ apiClient: api }));

import { describeFlags, resetTrackFlags, setTrackFlags } from "./audioService";

describe("the track flags", () => {
  it("are described in one line, naming who set them", () => {
    expect(describeFlags(null)).toBeNull();
    expect(describeFlags({})).toBeNull();
    expect(describeFlags({ vocal_state: "instrumental", set_by: "detected" })).toBe("Instrumental · detected");
    expect(describeFlags({ vocal_state: "vocal", language: "es", explicit_state: "clean", set_by: "admin" })).toBe("Vocal · ES · clean · set by an admin");
  });

  it("send only what changes, and reset through the delete route", async () => {
    api.put.mockResolvedValueOnce({ explicit_state: "clean" });
    await setTrackFlags(7, { explicit_state: "clean" });
    expect(api.put).toHaveBeenCalledWith("/api/tracks/7/flags", { explicit_state: "clean" });
    await resetTrackFlags(7);
    expect(api.delete).toHaveBeenCalledWith("/api/tracks/7/flags");
  });
});
