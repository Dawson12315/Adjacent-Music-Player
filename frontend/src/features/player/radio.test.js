import { describe, expect, it, vi } from "vitest";

import {
  REFILL_AHEAD,
  STATIONS_CHANGED_EVENT,
  announceStationsChanged,
  feedbackState,
  isRadioSource,
  isWideReason,
  radioAvailableFor,
  radioFeedbackAvailableFor,
  radioSource,
  reachNotice,
  reasonsByTrackId,
  stationBatchCandidates,
  stationKindLabel,
  stationLine,
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

describe("what the server offers", () => {
  it("has radio from API 10 or the capability, and feedback from 12", () => {
    expect(radioAvailableFor({ apiVersion: 9, capabilities: [] })).toBe(false);
    expect(radioAvailableFor({ apiVersion: 10, capabilities: [] })).toBe(true);
    expect(radioAvailableFor({ apiVersion: 0, capabilities: ["radio"] })).toBe(true);
    expect(radioFeedbackAvailableFor({ apiVersion: 11 })).toBe(false);
    expect(radioFeedbackAvailableFor({ apiVersion: 12 })).toBe(true);
    expect(REFILL_AHEAD).toBeGreaterThan(0);
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
    expect(stationSeedFor({ album: { name: "Blue Harbour", album_artist: "Fen" } }).seed_album_artist).toBe("Fen");
    expect(stationSeedFor({ artist: "Fen" })).toEqual({ seed_type: "artist", seed_artist: "Fen" });
    expect(stationSeedFor({ artist: { name: "Fen" } })).toEqual({ seed_type: "artist", seed_artist: "Fen" });
    expect(stationSeedFor({})).toBeNull();
  });
});

describe("station names and batches", () => {
  it("knows the kind, the seed's name, and keeps a batch in order without repeats", () => {
    expect(stationKindLabel({ seed_type: "album" })).toBe("Album radio");
    expect(stationSeedName({ name: "Fen radio" })).toBe("Fen");
    expect(stationSeedName({ name: "Fen" })).toBe("Fen");
    const batch = [{ id: 1 }, { id: 2 }, { id: 1 }, { id: null }, { id: 3 }];
    expect(stationBatchCandidates(batch, { excludeIds: new Set([3]) }).map((t) => t.id)).toEqual([1, 2]);
    expect(stationBatchCandidates(null)).toEqual([]);
    const reasons = reasonsByTrackId([{ id: 1, reason: "From Fen" }, { id: 2 }, { id: 1, reason: "Again" }]);
    expect(reasons.get("1")).toBe("Again");
    expect(reasons.has("2")).toBe(false);
  });

  it("writes the line under the name", () => {
    expect(stationLine({ kind: "Artist radio", position: 3, total: 20, live: true })).toBe(
      "Artist radio · 3 of 20 · more arrives as it plays",
    );
    expect(stationLine({ kind: "Artist radio", position: 3, total: 20, live: true, isLoop: true })).toBe(
      "Artist radio · 3 of 20 · repeat is on, so nothing more arrives",
    );
    expect(stationLine({ kind: "Album radio" })).toBe("Album radio");
  });
});

describe("reasons and reach", () => {
  it("tells a reason that reached wide from one that stayed close", () => {
    expect(isWideReason("Back around to Fen")).toBe(true);
    expect(isWideReason("From what you play most")).toBe(true);
    expect(isWideReason("Somewhere else in your library")).toBe(true);
    expect(isWideReason("Close to Fen")).toBe(false);
    expect(isWideReason("From Fen")).toBe(false);
    expect(isWideReason(null)).toBe(false);
  });

  it("has one notice per reach, naming the seed", () => {
    expect(reachNotice("again", "Fen")).toContain("coming back round");
    expect(reachNotice("library", "Fen")).toContain("across all of it");
    expect(reachNotice("listener", "Fen")).toContain("what you play most");
    expect(reachNotice("genre", "Fen")).toContain("a little wider");
    expect(reachNotice(null)).toContain("this seed");
  });
});

describe("feedback", () => {
  it("reads what was said about a track, by id and by artist", () => {
    const feedback = { more_track_ids: [3], less_track_ids: [9], less_artists: ["Fen"] };
    expect(feedbackState(feedback, { id: 3, artist: "fen" })).toEqual({ more: true, less: false, lessArtist: true });
    expect(feedbackState(feedback, { id: 9, artist: "Other" })).toEqual({ more: false, less: true, lessArtist: false });
    expect(feedbackState(null, { id: 9 })).toEqual({ more: false, less: false, lessArtist: false });
  });

  it("announces a change to the station list on the window", () => {
    const heard = vi.fn();
    window.addEventListener(STATIONS_CHANGED_EVENT, heard);
    announceStationsChanged();
    expect(heard).toHaveBeenCalledTimes(1);
    window.removeEventListener(STATIONS_CHANGED_EVENT, heard);
  });
});
