import { describe, expect, it } from "vitest";

import { normalizeTrack, normalizeTracks } from "./normalize";

// The endpoint a track came from determines whether genres and artists are populated.
// Conflating "no genres" with "this response doesn't carry genres" is what let the edit
// form submit an empty genre list and wipe a track's genres, since PATCH replaces them.
const FULL_ROW = {
  id: 1,
  title: "Song",
  artist: "Artist",
  album: "Album",
  genre: "Rock",
  genres: ["Rock", "Indie"],
  artists: ["Artist"],
  file_path: "/music/song.flac",
  album_artwork_path: "/uploads/albums/a.jpg",
};

// What GET /api/playlists/{id}/tracks actually returns: raw ORM columns.
const BARE_ROW = {
  id: 1,
  title: "Song",
  artist: "Artist",
  album: "Album",
  genre: "Rock",
  file_path: "/music/song.flac",
};

describe("normalizeTrack", () => {
  it("marks a track from a full endpoint as having authoritative metadata", () => {
    const track = normalizeTrack(FULL_ROW, { metadataComplete: true });

    expect(track.metadataComplete).toBe(true);
    expect(track.genres).toEqual(["Rock", "Indie"]);
  });

  it("marks a raw ORM row as incomplete, so its empty genres are not trusted", () => {
    const track = normalizeTrack(BARE_ROW, { metadataComplete: false });

    expect(track.metadataComplete).toBe(false);
    expect(track.genres).toEqual([]);
  });

  it("defaults to incomplete when the caller says nothing", () => {
    expect(normalizeTrack(BARE_ROW).metadataComplete).toBe(false);
  });

  it("fills every field the UI reads so components never see undefined", () => {
    const track = normalizeTrack(BARE_ROW, { metadataComplete: false });

    expect(track.artists).toEqual([]);
    expect(track.artwork_path).toBeNull();
    expect(track.album_artwork_path).toBeNull();
    expect(track.artist_artwork_path).toBeNull();
    expect(track.raw_title).toBeNull();
    expect(track.lastfm_tags_enriched).toBe(false);
  });

  it("keeps the recommendation explanation when one is attached", () => {
    const track = normalizeTrack({ ...BARE_ROW, debug: { reason_summary: "same artist" } });

    expect(track.debug.reason_summary).toBe("same artist");
  });

  it("omits the debug key entirely when there is none", () => {
    expect("debug" in normalizeTrack(BARE_ROW)).toBe(false);
  });

  it("returns null for a missing track", () => {
    expect(normalizeTrack(null)).toBeNull();
    expect(normalizeTrack(undefined)).toBeNull();
  });
});

describe("normalizeTracks", () => {
  it("normalises a list", () => {
    const tracks = normalizeTracks([FULL_ROW, BARE_ROW], { metadataComplete: true });

    expect(tracks).toHaveLength(2);
    expect(tracks.every((track) => track.metadataComplete)).toBe(true);
  });

  it("returns an empty array for a non-list, which some endpoints can produce", () => {
    expect(normalizeTracks(null)).toEqual([]);
    expect(normalizeTracks(undefined)).toEqual([]);
    expect(normalizeTracks({})).toEqual([]);
  });
});
