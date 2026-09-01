import { describe, expect, it } from "vitest";

import {
  isLikedSongsPlaylist,
  sortPlaylistsWithSystemFirst,
  upsertPlaylist,
} from "./playlists";

// The backend writes the system key as `liked_songs:{user_id}`. Three separate sorts
// used to compare against the bare legacy string, which never matched, so the system
// playlist silently lost its pinned position after any playlist edit.
const DUCKING_GOOD = { id: 1, name: "Ducking Good", system_key: "liked_songs:7" };
const ZEBRA = { id: 2, name: "Zebra", system_key: null };
const ALPHA = { id: 3, name: "Alpha", system_key: null };

describe("isLikedSongsPlaylist", () => {
  it("recognises the user-scoped system key", () => {
    expect(isLikedSongsPlaylist(DUCKING_GOOD)).toBe(true);
  });

  it("does not treat a normal playlist as the system one", () => {
    expect(isLikedSongsPlaylist(ZEBRA)).toBe(false);
  });

  it("tolerates a missing playlist", () => {
    expect(isLikedSongsPlaylist(null)).toBe(false);
    expect(isLikedSongsPlaylist(undefined)).toBe(false);
    expect(isLikedSongsPlaylist({})).toBe(false);
  });
});

describe("sortPlaylistsWithSystemFirst", () => {
  it("pins the system playlist first regardless of its name", () => {
    const sorted = sortPlaylistsWithSystemFirst([ZEBRA, ALPHA, DUCKING_GOOD]);

    expect(sorted.map((item) => item.name)).toEqual(["Ducking Good", "Alpha", "Zebra"]);
  });

  it("sorts the rest alphabetically", () => {
    const sorted = sortPlaylistsWithSystemFirst([ZEBRA, ALPHA]);

    expect(sorted.map((item) => item.name)).toEqual(["Alpha", "Zebra"]);
  });

  it("does not mutate the input", () => {
    const input = [ZEBRA, DUCKING_GOOD];
    sortPlaylistsWithSystemFirst(input);

    expect(input[0]).toBe(ZEBRA);
  });
});

describe("upsertPlaylist", () => {
  it("keeps the system playlist pinned after adding a playlist", () => {
    const result = upsertPlaylist([DUCKING_GOOD, ZEBRA], ALPHA);

    expect(result.map((item) => item.name)).toEqual(["Ducking Good", "Alpha", "Zebra"]);
  });

  it("keeps the system playlist pinned after a rename", () => {
    const renamed = { ...ZEBRA, name: "Aardvark" };
    const result = upsertPlaylist([DUCKING_GOOD, ZEBRA], renamed);

    expect(result.map((item) => item.name)).toEqual(["Ducking Good", "Aardvark"]);
    expect(result).toHaveLength(2);
  });

  it("replaces in place rather than duplicating", () => {
    const updated = { ...ALPHA, artwork_path: "/uploads/playlist_artwork/a.png" };
    const result = upsertPlaylist([ALPHA, ZEBRA], updated);

    expect(result).toHaveLength(2);
    expect(result.find((item) => item.id === ALPHA.id).artwork_path).toBe(
      "/uploads/playlist_artwork/a.png",
    );
  });
});
