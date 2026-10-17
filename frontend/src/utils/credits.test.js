import { describe, expect, it } from "vitest";

import { creditLine, recordArtist } from "./credits";

describe("creditLine", () => {
  it("names every credit, lead first", () => {
    expect(creditLine({ artist: "Kodak Black", artists: ["Kodak Black", "1900Rugrat"] })).toBe("Kodak Black, 1900Rugrat");
  });
  it("falls back to the lead, then to Unknown Artist", () => {
    expect(creditLine({ artist: "Solo", artists: [] })).toBe("Solo");
    expect(creditLine({ artist: "Solo" })).toBe("Solo");
    expect(creditLine({})).toBe("Unknown Artist");
    expect(creditLine(null)).toBe("Unknown Artist");
  });
});

describe("recordArtist", () => {
  it("prefers the album artist", () => {
    expect(recordArtist({ artist: "Perf", album_artist: "Various Artists" })).toBe("Various Artists");
    expect(recordArtist({ artist: "Perf" })).toBe("Perf");
    expect(recordArtist({})).toBeNull();
  });
});
