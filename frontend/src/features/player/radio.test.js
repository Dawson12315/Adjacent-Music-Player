import { describe, expect, it } from "vitest";

import {
  isRadioSource,
  radioSource,
  reasonsByTrackId,
  stationBatchCandidates,
  stationKindLabel,
  stationSeedFor,
  stationSeedName,
} from "./radio";

describe("radioSource", () => {
  it("plays under the radio source with the station as its id", () => {
    expect(radioSource(7)).toEqual({ source_type: "radio", source_id: 7 });
    expect(isRadioSource(radioSource(7))).toBe(true);
    expect(isRadioSource({ source_type: "radio", source_id: null })).toBe(false);
    expect(isRadioSource({ source_type: "album", source_id: null })).toBe(false);
  });
});

describe("stationSeedFor", () => {
  it("seeds from a track, an album or an artist", () => {
    expect(stationSeedFor({ track: { id: 3 } })).toEqual({ seed_type: "track", seed_track_id: 3 });
    expect(stationSeedFor({ album: { name: "Blue Harbour", artist: "Fen" } })).toEqual({
      seed_type: "album",
      seed_album: "Blue Harbour",
      seed_album_artist: "Fen",
    });
    expect(stationSeedFor({ artist: "Fen" })).toEqual({ seed_type: "artist", seed_artist: "Fen" });
    expect(stationSeedFor({})).toBeNull();
  });
});

describe("station names and batches", () => {
  it("knows the kind, the seed's name, and keeps a batch in order without repeats", () => {
    expect(stationKindLabel({ seed_type: "album" })).toBe("Album radio");
    expect(stationSeedName({ name: "Fen radio" })).toBe("Fen");
    const batch = [{ id: 1 }, { id: 2 }, { id: 1 }, { id: 3 }];
    expect(stationBatchCandidates(batch, { excludeIds: new Set([3]) }).map((t) => t.id)).toEqual([1, 2]);
    expect(reasonsByTrackId([{ id: 1, reason: "From Fen" }, { id: 2 }]).get("1")).toBe("From Fen");
  });
});
