import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const USER = { id: 1, username: "admin", role: "admin", is_active: true };

const TRACKS = [
  {
    id: 1,
    title: "Bohemian Rhapsody",
    artist: "Queen",
    album: "A Night at the Opera",
    genre: "Rock",
    genres: ["Rock"],
    artists: ["Queen"],
    file_path: "/music/queen.flac",
  },
  {
    id: 2,
    title: "Blue Monday",
    artist: "New Order",
    album: "Power, Corruption & Lies",
    genre: "Synth-pop",
    genres: ["Synth-pop"],
    artists: ["New Order"],
    file_path: "/music/neworder.flac",
  },
];

const PLAYLISTS = [
  { id: 11, name: "Road Trip", is_system: false, system_key: null },
  { id: 10, name: "Ducking Good", is_system: true, system_key: "liked_songs:1" },
];

const EMPTY_PLAYBACK = {
  current_track_id: null,
  queue_index: -1,
  current_time_seconds: 0,
  is_playing: false,
  is_shuffle: false,
  is_loop: false,
  queue_track_ids: [],
};

const SUMMARY = {
  total_plays: 2776,
  total_skips: 938,
  total_completions: 611,
  distinct_tracks_played: 1000,
  distinct_artists_played: 320,
  days_active: 25,
  first_played_at: "2026-04-20T10:00:00",
  last_played_at: "2026-05-19T22:00:00",
  completion_rate: 0.22,
  skip_rate: 0.25,
  estimated_listening_seconds: 111530,
  current_streak_days: 3,
  longest_streak_days: 9,
};

/**
 * Only the network is stubbed. Everything above it — apiClient, the services, the
 * normalizers, the contexts, routing and every component — runs for real.
 */
function stubApi({ signedIn = true, overrides = {} } = {}) {
  const routes = {
    "/api/auth/setup-status": { admin_exists: true },
    "/api/auth/me": signedIn ? USER : { __status: 401, detail: "Not authenticated" },
    "/api/auth/login": { user: USER },
    "/api/auth/logout": { message: "Logged out" },

    "/api/tracks/count": { count: TRACKS.length },
    "/api/artists": ["New Order", "Queen"],
    "/api/albums": ["A Night at the Opera", "Power, Corruption & Lies"],
    "/api/genres": ["Rock", "Synth-pop"],
    "/api/playlists": PLAYLISTS,
    "/api/albums/artwork": { artwork: {} },
    "/api/artists/artwork": { artwork: {} },
    "/api/playback": EMPTY_PLAYBACK,

    "/api/recommendations/for-you": [],
    "/api/stats/summary": SUMMARY,
    "/api/stats/plays-over-time": [{ date: "2026-05-19", plays: 12 }],
    "/api/stats/top-artists": [{ name: "Queen", play_count: 120 }],
    "/api/stats/top-albums": [{ name: "A Night at the Opera", artist: "Queen", play_count: 90 }],
    "/api/stats/by-source": [{ source: "library", plays: 4207 }],
    "/api/stats/by-hour": Array.from({ length: 24 }, (_, hour) => ({ hour, plays: hour })),
    "/api/stats/overview": {
      top_played: [],
      most_liked: [],
      most_skipped: [],
      recently_played: [],
      top_genres: [{ name: "Rock", play_count: 300 }],
    },
    ...overrides,
  };

  globalThis.fetch = vi.fn(async (url) => {
    const { pathname, searchParams } = new URL(url);

    let body = routes[pathname];

    if (body === undefined) {
      if (pathname === "/api/tracks") {
        // Paged envelope — the app always supplies a limit now.
        const limit = Number(searchParams.get("limit") || 60);
        const search = (searchParams.get("search") || "").toLowerCase();
        const matches = search
          ? TRACKS.filter((t) =>
              [t.title, t.artist, t.album].some((v) => v?.toLowerCase().includes(search)),
            )
          : TRACKS;

        body = {
          items: matches.slice(0, limit),
          total: matches.length,
          limit,
          offset: 0,
          has_more: false,
        };
      } else if (pathname.endsWith("-detailed")) {
        body = TRACKS.map((t) => ({ ...t, play_count: 42, like_count: 3, skip_count: 1 }));
      } else if (/^\/api\/artists\/[^/]+\/tracks$/.test(pathname)) {
        const name = decodeURIComponent(pathname.split("/")[3]);
        body = TRACKS.filter((t) => t.artist === name);
      } else if (/^\/api\/albums\/[^/]+\/tracks$/.test(pathname)) {
        const name = decodeURIComponent(pathname.split("/")[3]);
        body = TRACKS.filter((t) => t.album === name);
      } else if (pathname.endsWith("/genres")) {
        body = [];
      } else if (pathname.endsWith("/similar")) {
        body = [];
      } else if (pathname.includes("/liked-songs/tracks/")) {
        body = { liked: false };
      } else if (pathname.endsWith("/tracks")) {
        body = [];
      } else {
        body = {};
      }
    }

    const status = body?.__status ?? 200;

    return {
      ok: status >= 200 && status < 300,
      status,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => body,
      text: async () => JSON.stringify(body),
    };
  });
}

/** The actual <button>/<a> inside a sidebar entry. */
function sidebarLink(name) {
  const match = Array.from(document.querySelectorAll(".nav-item")).find(
    (node) => node.textContent.trim() === name,
  );

  if (!match) throw new Error(`No sidebar link named "${name}"`);
  return match;
}

async function renderAt(path = "/") {
  window.history.pushState({}, "", path);
  render(<App />);
  await screen.findByRole("navigation", { name: "Library" });
}

describe("Adjacent", () => {
  beforeEach(() => {
    stubApi();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.history.pushState({}, "", "/");
  });

  it("shows the sign-in screen when there is no session", async () => {
    stubApi({ signedIn: false });

    render(<App />);

    expect(await screen.findByText("Welcome back")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("signs in and reaches the app", async () => {
    stubApi({ signedIn: false });

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("Welcome back");
    await user.type(screen.getByLabelText(/^password$/i), "hunter2");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("navigation", { name: "Library" })).toBeInTheDocument();
  });

  it("lands on the home page, not a raw track list", async () => {
    await renderAt("/");

    expect(await screen.findByRole("heading", { name: /Good (morning|afternoon|evening)/ }))
      .toBeInTheDocument();
  });

  it("shows the library on the tracks route", async () => {
    await renderAt("/tracks");

    expect(await screen.findByText("Bohemian Rhapsody")).toBeInTheDocument();
    expect(screen.getByText("Blue Monday")).toBeInTheDocument();
  });

  it("requests a paged track list rather than the whole library", async () => {
    await renderAt("/tracks");
    await screen.findByText("Bohemian Rhapsody");

    const trackCalls = globalThis.fetch.mock.calls
      .map(([url]) => new URL(url))
      .filter((url) => url.pathname === "/api/tracks");

    expect(trackCalls.length).toBeGreaterThan(0);
    // Every call must carry a limit; an unbounded call is the 21 MB regression.
    trackCalls.forEach((url) => {
      expect(url.searchParams.get("limit")).toBeTruthy();
    });
  });

  it("fetches artwork in bulk, not per album", async () => {
    await renderAt("/tracks");
    await screen.findByText("Bohemian Rhapsody");

    const paths = globalThis.fetch.mock.calls.map(([url]) => new URL(url).pathname);

    expect(paths).toContain("/api/albums/artwork");
    expect(paths.filter((p) => /^\/api\/albums\/.+\/artwork$/.test(p))).toHaveLength(0);
  });

  it("plays a track and shows it in the player bar", async () => {
    const user = userEvent.setup();
    await renderAt("/tracks");

    await user.click(await screen.findByText("Bohemian Rhapsody"));

    const playerBar = document.querySelector(".player-bar");

    await waitFor(() =>
      expect(within(playerBar).getByText("Bohemian Rhapsody")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
  });

  it("advances to the next track and back again", async () => {
    const user = userEvent.setup();
    await renderAt("/tracks");

    await user.click(await screen.findByText("Bohemian Rhapsody"));
    const playerBar = document.querySelector(".player-bar");

    await waitFor(() =>
      expect(within(playerBar).getByText("Bohemian Rhapsody")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "Next track" }));
    await waitFor(() =>
      expect(within(playerBar).getByText("Blue Monday")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "Previous track" }));
    await waitFor(() =>
      expect(within(playerBar).getByText("Bohemian Rhapsody")).toBeInTheDocument(),
    );
  });

  it("searches server-side and keeps the term in the URL", async () => {
    const user = userEvent.setup();
    await renderAt("/tracks");
    await screen.findByText("Bohemian Rhapsody");

    await user.type(screen.getByLabelText("Search tracks"), "blue");

    await waitFor(() => expect(window.location.search).toContain("q=blue"));

    await waitFor(() => {
      const searched = globalThis.fetch.mock.calls
        .map(([url]) => new URL(url))
        .some((url) => url.pathname === "/api/tracks" && url.searchParams.get("search") === "blue");

      expect(searched).toBe(true);
    });
  });

  it("navigates to an artist and filters to their tracks", async () => {
    const user = userEvent.setup();
    await renderAt("/tracks");

    await user.click(sidebarLink("Artists"));
    await user.click(await screen.findByText("Queen"));

    await waitFor(() => expect(window.location.pathname).toBe("/artists/Queen"));
    expect(await screen.findByRole("heading", { name: "Queen" })).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByText("Blue Monday")).not.toBeInTheDocument());
  });

  it("restores a view straight from its URL", async () => {
    await renderAt("/genres");

    expect(await screen.findByRole("heading", { name: "Genres" })).toBeInTheDocument();
    expect(screen.getAllByText("Rock").length).toBeGreaterThan(0);
  });

  it("pins the system playlist above the others in the sidebar", async () => {
    await renderAt("/");

    const names = Array.from(
      document.querySelectorAll(".playlist-item__name"),
    ).map((node) => node.textContent);

    expect(names).toContain("Ducking Good");
    expect(names.indexOf("Ducking Good")).toBeLessThan(names.indexOf("Road Trip"));
  });

  it("shows real numbers on the insights page", async () => {
    await renderAt("/insights");

    // The old page showed the length of a list here, capped at ten.
    expect(await screen.findByText("2,776")).toBeInTheDocument();
    expect(screen.getByText("22%")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();
  });

  it("opens the queue panel from the player bar", async () => {
    const user = userEvent.setup();
    await renderAt("/tracks");

    await user.click(await screen.findByText("Bohemian Rhapsody"));
    await user.click(screen.getByRole("button", { name: "Queue" }));

    expect(await screen.findByRole("heading", { name: "Queue" })).toBeInTheDocument();
  });

  it("returns to the sign-in screen when the session expires", async () => {
    await renderAt("/tracks");
    await screen.findByText("Bohemian Rhapsody");

    const { request } = await import("./services/apiClient");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Not authenticated" }),
      text: async () => "{}",
    });

    await request("/api/tracks").catch(() => {});

    expect(await screen.findByText(/session expired/i)).toBeInTheDocument();
  });
});
