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

/**
 * The network is the only thing stubbed. Everything above it — apiClient, the services,
 * the normalizers, the contexts, routing and every component — runs for real, which is
 * what makes this worth having as a regression net for the composition.
 */
function stubApi({ signedIn = true, overrides = {} } = {}) {
  const routes = {
    "/api/auth/setup-status": { admin_exists: true },
    "/api/auth/me": signedIn ? USER : { __status: 401, detail: "Not authenticated" },
    "/api/auth/login": { user: USER },
    "/api/auth/logout": { message: "Logged out" },
    "/api/tracks": TRACKS,
    "/api/artists": ["New Order", "Queen"],
    "/api/albums": ["A Night at the Opera", "Power, Corruption & Lies"],
    "/api/genres": ["Rock", "Synth-pop"],
    "/api/playlists": PLAYLISTS,
    "/api/playback": EMPTY_PLAYBACK,
    "/api/stats/overview": {
      top_played: [],
      most_liked: [],
      most_skipped: [],
      recently_played: [],
      top_genres: [],
    },
    ...overrides,
  };

  globalThis.fetch = vi.fn(async (url) => {
    const { pathname } = new URL(url);

    let body =
      routes[pathname] ??
      (pathname.endsWith("/artwork")
        ? { artwork_path: null }
        : pathname.endsWith("/similar")
        ? []
        : pathname.includes("/liked-songs/tracks/")
        ? { liked: false }
        : pathname.endsWith("/tracks")
        ? []
        : {});

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

/** The actual <button> inside a sidebar entry, not its role="button" wrapper. */
function sidebarLink(name) {
  const match = Array.from(
    document.querySelectorAll(".playlist-sidebar-item__name-button"),
  ).find((node) => node.textContent === name);

  if (!match) {
    throw new Error(`No sidebar link named "${name}"`);
  }

  return match;
}

async function renderSignedIn() {
  window.history.pushState({}, "", "/");
  render(<App />);
  await screen.findByText("Bohemian Rhapsody");
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

  it("signs in and loads the library", async () => {
    stubApi({ signedIn: false });

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("Welcome back");
    await user.type(screen.getByLabelText(/password/i), "hunter2");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Bohemian Rhapsody")).toBeInTheDocument();
  });

  it("renders the library with its track count", async () => {
    await renderSignedIn();

    expect(screen.getByRole("heading", { name: "Your Music" })).toBeInTheDocument();
    expect(screen.getByText("2 tracks")).toBeInTheDocument();
    expect(screen.getByText("Blue Monday")).toBeInTheDocument();
  });

  it("plays a track and shows it in the player bar", async () => {
    const user = userEvent.setup();
    await renderSignedIn();

    await user.click(screen.getByText("Bohemian Rhapsody"));

    const playerBar = document.querySelector(".player-bar");

    await waitFor(() =>
      expect(within(playerBar).getByText("Bohemian Rhapsody")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
  });

  it("advances to the next track and back again", async () => {
    const user = userEvent.setup();
    await renderSignedIn();

    await user.click(screen.getByText("Bohemian Rhapsody"));

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

  it("filters the library from the search box", async () => {
    const user = userEvent.setup();
    await renderSignedIn();

    await user.type(screen.getByLabelText("Search tracks"), "blue");

    await waitFor(() =>
      expect(screen.queryByText("Bohemian Rhapsody")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Blue Monday")).toBeInTheDocument();
  });

  it("keeps the search term in the URL", async () => {
    const user = userEvent.setup();
    await renderSignedIn();

    await user.type(screen.getByLabelText("Search tracks"), "blue");

    await waitFor(() => expect(window.location.search).toContain("q=blue"));
  });

  it("navigates to an artist and filters to their tracks", async () => {
    const user = userEvent.setup();
    await renderSignedIn();

    // Queried as a real <button> because the sidebar item's wrapper div also carries
    // role="button" with the same accessible name — nested interactive elements that the
    // accessibility pass still has to unpick.
    await user.click(sidebarLink("Artists"));
    await user.click(await screen.findByText("Queen"));

    await waitFor(() => expect(window.location.pathname).toBe("/artists/Queen"));
    expect(await screen.findByRole("heading", { name: "Queen" })).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.queryByText("Blue Monday")).not.toBeInTheDocument(),
    );
  });

  it("restores a view straight from its URL", async () => {
    window.history.pushState({}, "", "/genres");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Genres" })).toBeInTheDocument();
    // Rock is both the dominant-genre feature card and a card in the grid.
    expect(screen.getAllByText("Rock").length).toBeGreaterThan(0);
    expect(screen.getByText("Synth-pop")).toBeInTheDocument();
  });

  it("pins the system playlist above the others in the sidebar", async () => {
    await renderSignedIn();

    const names = Array.from(
      document.querySelectorAll(".playlist-sidebar-item__name-button"),
    ).map((node) => node.textContent);

    expect(names).toContain("Ducking Good");
    expect(names.indexOf("Ducking Good")).toBeLessThan(names.indexOf("Road Trip"));
  });

  it("opens the queue panel from the player bar", async () => {
    const user = userEvent.setup();
    await renderSignedIn();

    await user.click(screen.getByText("Bohemian Rhapsody"));
    await user.click(screen.getByRole("button", { name: "Queue" }));

    expect(await screen.findByRole("heading", { name: "Queue" })).toBeInTheDocument();
    expect(screen.getByText("Now Playing")).toBeInTheDocument();
  });

  it("returns to the sign-in screen when the session expires", async () => {
    await renderSignedIn();

    // A 401 from any request is what an expired seven-day cookie looks like. This used
    // to leave a fully-rendered but dead UI with the failure going only to the console.
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
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });
});
