import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const TRACKS = Array.from({ length: 12 }, (_, i) => ({
  id: i + 1,
  title: `Song ${i + 1}`,
  artist: "Someone",
  album: "Somewhere",
}));

const home = {
  recentlyPlayed: [],
  topPlayed: [],
  topGenres: [],
  forYou: TRACKS,
  isLoading: false,
  isLoadingForYou: true,
  refreshForYou: vi.fn(),
};

vi.mock("./useHomeData", () => ({
  useHomeData: () => home,
  getGreeting: () => "Good morning",
}));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ currentUser: { username: "dawson" } }) }));
vi.mock("../../contexts/LibraryContext", () => ({
  useLibrary: () => ({ playlists: [], albumArtworkMap: {}, artists: [], albums: [], trackCount: 0 }),
}));
const player = { playTrack: vi.fn(), playStation: vi.fn() };
vi.mock("../../contexts/PlayerContext", () => ({ usePlayer: () => player }));

import { HomeView } from "./HomeView";

function renderHome() {
  return render(
    <MemoryRouter>
      <HomeView />
    </MemoryRouter>,
  );
}

describe("the For you rail while it reshuffles", () => {
  it("keeps the twelve cards on screen, dimmed, and says what is happening", () => {
    home.isLoadingForYou = true;
    home.forYou = TRACKS;
    renderHome();

    expect(screen.getByText("Song 1")).toBeInTheDocument();
    expect(screen.getByText("Song 12")).toBeInTheDocument();
    expect(screen.getByText("Picking new songs…")).toBeInTheDocument();
    const scroller = screen.getByText("Song 1").closest(".rail__scroller");
    expect(scroller).toHaveClass("rail__scroller--refreshing");
    expect(scroller).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "Refresh recommendations" })).toBeDisabled();
  });

  it("stays on the page with a message when the answer is empty", () => {
    home.isLoadingForYou = false;
    home.forYou = [];
    renderHome();

    expect(screen.getByText("For you")).toBeInTheDocument();
    expect(screen.getByText(/Nothing new to suggest yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh recommendations" })).toBeEnabled();
  });

  it("shows the real cards, untouched, once the answer lands", () => {
    home.isLoadingForYou = false;
    home.forYou = TRACKS;
    renderHome();

    const scroller = screen.getByText("Song 1").closest(".rail__scroller");
    expect(scroller).not.toHaveClass("rail__scroller--refreshing");
    expect(screen.queryByText("Picking new songs…")).not.toBeInTheDocument();
  });
});

describe("the Recent stations rail", () => {
  it("lists the stations played lately and plays one on a click", () => {
    home.isLoadingForYou = false;
    home.forYou = [];
    home.stations = [
      { id: 4, name: "Fen radio", seed_type: "artist", artwork_path: null },
      { id: 5, name: "Blue Harbour radio", seed_type: "album", artwork_path: "/uploads/bh.jpg" },
    ];
    renderHome();

    expect(screen.getByText("Recent stations")).toBeInTheDocument();
    expect(screen.getByText("Artist radio")).toBeInTheDocument();
    expect(screen.getByText("Album radio")).toBeInTheDocument();
    screen.getByRole("button", { name: "Play Fen radio" }).click();
    expect(player.playStation).toHaveBeenCalledWith(home.stations[0]);
  });

  it("is absent until a station has been played", () => {
    home.stations = [];
    renderHome();
    expect(screen.queryByText("Recent stations")).not.toBeInTheDocument();
  });
});
