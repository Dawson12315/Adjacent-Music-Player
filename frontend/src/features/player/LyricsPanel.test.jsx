import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { player, progress, auth, service } = vi.hoisted(() => ({
  player: { currentTrack: { id: 7, title: "Long Way Round" } },
  progress: { currentTime: 6, duration: 90, seek: vi.fn() },
  auth: { currentUser: { role: "admin" } },
  service: {
    getLyrics: vi.fn(),
    requestLyrics: vi.fn(),
    saveLyrics: vi.fn(),
    resetLyrics: vi.fn(),
  },
}));

vi.mock("../../contexts/PlayerContext", () => ({ usePlayer: () => player, usePlayerProgress: () => progress }));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../../contexts/NotificationContext", () => ({ useNotifications: () => ({ notify: vi.fn() }) }));
vi.mock("../../services/lyricsService", async () => {
  const actual = await vi.importActual("../../services/lyricsService");
  return { ...actual, ...service };
});

import { LyricsPanel } from "./LyricsPanel";

const TIMED = {
  trackId: 7,
  source: "embedded",
  syncedSource: null,
  plain: "first line\nsecond line\nthird line",
  synced: [{ t: 1, line: "first line" }, { t: 5, line: "second line" }, { t: 9, line: "third line" }],
  generated: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  Element.prototype.scrollIntoView = vi.fn();
});

describe("the lyrics panel", () => {
  it("lights the line being sung, seeks on a click, and names the source", async () => {
    service.getLyrics.mockResolvedValueOnce(TIMED);
    render(<LyricsPanel />);

    const active = await screen.findByText("second line");
    expect(active).toHaveAttribute("aria-current", "true");
    expect(screen.getByText("first line")).not.toHaveAttribute("aria-current");
    fireEvent.click(screen.getByText("third line"));
    expect(progress.seek).toHaveBeenCalledWith(9);
    expect(screen.getByText("From the file")).toBeInTheDocument();
  });

  it("offers the server's help when there are none, then polls", async () => {
    service.getLyrics.mockResolvedValueOnce({ none: true, generation: { state: "available" } });
    service.requestLyrics.mockResolvedValueOnce({ state: "queued" });
    render(<LyricsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Generate on your server" }));
    await waitFor(() => expect(service.requestLyrics).toHaveBeenCalledWith(7));
    expect(await screen.findByText(/Your server is writing them down/)).toBeInTheDocument();
  });

  it("lets an admin paste words, stamp every line as it plays, and saves them timed", async () => {
    service.getLyrics.mockResolvedValueOnce({ none: true, generation: { state: "off" } });
    service.saveLyrics.mockResolvedValueOnce({ ...TIMED, source: "user", syncedSource: "user" });
    render(<LyricsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Add lyrics" }));
    fireEvent.change(screen.getByLabelText("Lyrics text"), { target: { value: "one\ntwo" } });
    expect(screen.getByText("0 / 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stamp" }));
    progress.currentTime = 12;
    fireEvent.click(screen.getByRole("button", { name: "Stamp" }));
    expect(screen.getByText("Every line is timed.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(service.saveLyrics).toHaveBeenCalledWith(7, {
      plain: "one\ntwo",
      synced: [{ t: 6, line: "one" }, { t: 6, line: "two" }],
    }));
    expect(await screen.findByText("Edited in Adjacent")).toBeInTheDocument();
  });

  it("lets an admin regenerate what the server produced, and says so while it works", async () => {
    service.getLyrics.mockResolvedValueOnce({ ...TIMED, source: "transcribed", syncedSource: "transcribed", generated: true, model: "base" });
    service.requestLyrics.mockResolvedValueOnce({ state: "queued" });
    render(<LyricsPanel />);

    await screen.findByText("first line");
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    await waitFor(() => expect(service.requestLyrics).toHaveBeenCalledWith(7, { force: true }));
    // A transcription is gone until the new one arrives; the panel shows the work in progress.
    expect(await screen.findByText(/Your server is writing them down/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Regenerate" })).toBeNull();
  });

  it("re-times the file's words in place, keeping them on screen while the server works", async () => {
    const aligned = { ...TIMED, syncedSource: "aligned", generated: true, model: "base" };
    service.getLyrics.mockResolvedValueOnce(aligned);
    service.requestLyrics.mockResolvedValueOnce({ state: "queued" });
    render(<LyricsPanel />);

    await screen.findByText("first line");
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    await waitFor(() => expect(service.requestLyrics).toHaveBeenCalledWith(7, { force: true }));
    expect(screen.getByText("first line")).toBeInTheDocument();
    expect(await screen.findByText("Your server is redoing these…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Regenerate" })).toBeNull();
  });

  it("does not offer Regenerate for words that came from the file", async () => {
    service.getLyrics.mockResolvedValueOnce(TIMED);
    render(<LyricsPanel />);
    await screen.findByText("first line");
    expect(screen.queryByRole("button", { name: "Regenerate" })).toBeNull();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("hides the edit controls from a listener", async () => {
    auth.currentUser = { role: "user" };
    service.getLyrics.mockResolvedValueOnce(TIMED);
    render(<LyricsPanel />);
    await screen.findByText("first line");
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    auth.currentUser = { role: "admin" };
  });
});
