import { describe, expect, it } from "vitest";

import { getAlbumArtworkPath, getAlbumKey, resolveAlbumArtwork } from "./artwork";

const SEP = "";

describe("album artwork keys", () => {
  it("names one artist's record, and the bare title without an artist", () => {
    expect(getAlbumKey("Greatest  Hits", "The Band")).toBe(`greatest hits${SEP}the band`);
    expect(getAlbumKey("Greatest Hits")).toBe("greatest hits");
    expect(getAlbumKey("Greatest Hits", "")).toBe("greatest hits");
    expect(getAlbumKey("", "The Band")).toBe("");
  });

  it("prefers the record's own picture over the title-wide one", () => {
    const map = {
      "greatest hits": "/uploads/albums/shared.jpg",
      [`greatest hits${SEP}the band`]: "/uploads/albums/band.jpg",
    };

    expect(getAlbumArtworkPath("Greatest Hits", map, "The Band")).toBe("/uploads/albums/band.jpg");
    // Set before records were told apart: still shows until this record gets its own.
    expect(getAlbumArtworkPath("Greatest Hits", map, "Someone Else")).toBe("/uploads/albums/shared.jpg");
    expect(getAlbumArtworkPath("Other", map, "The Band")).toBe("");

    expect(resolveAlbumArtwork("Greatest Hits", map, "The Band").type).toBe("image");
    expect(resolveAlbumArtwork("Other", map, "The Band").type).not.toBe("image");
  });
});
