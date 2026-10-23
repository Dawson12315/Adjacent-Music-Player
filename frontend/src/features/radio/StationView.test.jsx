import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const tracks = [
  { id: 3, title: "Second Light", artist: "Fen", album: "Low Country" },
  { id: 9, title: "Long Way Round", artist: "The Tessellations", album: "Blue Harbour" },
  { id: 6, title: "Opening", artist: "Modular Cassette", album: "Copper Wire" },
];

const player = {
  radioStation: { id: 4, name: "Fen radio", seed_type: "artist", artwork_path: null },
  radioReasons: { 3: "From Fen", 9: "Fits your ambient taste", 6: "Played around Fen in your sessions" },
  queue: tracks,
  queueIndex: 0,
  currentTrack: tracks[0],
  isPlaying: true,
  togglePlay: vi.fn(),
  next: vi.fn(),
  jumpTo: vi.fn(),
  fetchStationBatch: vi.fn(() => Promise.resolve(true)),
  playStation: vi.fn(() => Promise.resolve(true)),
};

vi.mock("../../contexts/PlayerContext", () => ({ usePlayer: () => player }));
vi.mock("../../contexts/LibraryContext", () => ({ useLibrary: () => ({ albumArtworkMap: {} }) }));
vi.mock("../../services/radioService", () => ({
  getStation: vi.fn(() => Promise.resolve({ id: 7, name: "Blue Harbour radio", seed_type: "album" })),
}));

import { StationView } from "./StationView";

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/radio/:stationId" element={<StationView />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("the station page", () => {
  it("shows the playing station, its place in the batch, and every track with its reason", () => {
    renderAt("/radio/4");
    expect(screen.getAllByText("Fen radio").length).toBeGreaterThan(0);
    expect(screen.getByText("Artist radio · 1 of 3 · more arrives as it plays")).toBeInTheDocument();
    expect(screen.getByText("From Fen")).toBeInTheDocument();
    expect(screen.getByText("Fits your ambient taste")).toBeInTheDocument();
    expect(screen.getByText("Played around Fen in your sessions")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Play Opening" }));
    expect(player.jumpTo).toHaveBeenCalledWith(2);
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(player.togglePlay).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(player.next).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Fresh batch" }));
    expect(player.fetchStationBatch).toHaveBeenCalled();
  });

  it("offers to play a station that is not the one playing", async () => {
    renderAt("/radio/7");
    expect(await screen.findByRole("heading", { level: 1, name: "Blue Harbour radio" })).toBeInTheDocument();
    expect(screen.getByText("Play the station to see what it lines up.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Play this station" }));
    expect(player.playStation).toHaveBeenCalledWith(expect.objectContaining({ id: 7 }));
  });
});
