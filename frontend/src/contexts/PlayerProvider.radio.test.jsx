import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The provider's station behaviour, with the audio element, the server and
 * the handoff hook stood in for. What a station is in the browser: the seed
 * plays, the batch appends, the next batch is asked for ahead of the end,
 * a skip on the last track continues the station, plays are reported when
 * heard, "Fresh batch" replaces what is up next, and a word against a
 * track takes it out of the queue.
 */

const t = (id, artist = "Someone") => ({ id, title: `Song ${id}`, artist, album: "Somewhere" });

const { mocks } = vi.hoisted(() => {
  const notify = vi.fn();
  const audioEl = { currentTime: 0, ended: false, duration: 0, play: vi.fn(), pause: vi.fn() };
  // One object for the element hook's answer: its functions must keep their
  // identity across renders, as the real hook's do, or effects keyed on
  // them re-run forever.
  const audio = {
    audioRef: { current: audioEl },
    currentTime: 0,
    duration: 0,
    seek: vi.fn(),
    requestSeek: vi.fn(),
    hasPendingSeek: () => false,
    hasSource: () => true,
    handleTimeUpdate: vi.fn(),
    handleLoadedMetadata: vi.fn(),
    handleError: vi.fn(),
  };
  const handoff = {
    available: false,
    isActiveHere: true,
    activeDeviceId: null,
    stale: false,
    claim: vi.fn(),
    reportPosition: vi.fn(),
    leaseKnown: true,
    sendCommand: vi.fn(),
    remote: null,
    me: null,
  };
  const events = { resetForTrack: vi.fn(), skipped: vi.fn(), completed: vi.fn(), playStarted: vi.fn(), likeChanged: vi.fn() };
  // The signed-in user is state in the real app, one object for the session.
  const user = { id: 1, username: "dawson" };
  return {
    mocks: {
      notify,
      user,
      audioEl,
      audio,
      handoff,
      events,
      saved: {
        queueTrackIds: [],
        currentTrackId: null,
        queueIndex: -1,
        isShuffle: false,
        isLoop: false,
        sourceType: "library",
        sourceId: null,
        currentTimeSeconds: 0,
      },
      tracksById: vi.fn(() => Promise.resolve([])),
      radio: {
        createStation: vi.fn(),
        getStation: vi.fn(),
        getStationLineup: vi.fn(),
        getStationNext: vi.fn(),
        reportStationPlays: vi.fn(() => Promise.resolve({ ok: true })),
        giveStationFeedback: vi.fn(),
        takeBackStationFeedback: vi.fn(),
        deleteStation: vi.fn(() => Promise.resolve({ ok: true })),
      },
    },
  };
});

vi.mock("../hooks/useAudioElement", () => ({ useAudioElement: () => mocks.audio }));
vi.mock("../hooks/useHandoff", () => ({ useHandoff: () => mocks.handoff }));
vi.mock("../hooks/usePlaybackPersistence", () => ({ usePlaybackPersistence: () => {} }));
vi.mock("../hooks/useMediaSession", () => ({ useMediaSession: () => {} }));
vi.mock("../hooks/useLastfmScrobbler", () => ({ useLastfmScrobbler: () => {} }));
vi.mock("../hooks/useListeningEvents", () => ({ useListeningEvents: () => mocks.events }));
vi.mock("./AuthContext", () => ({ useAuth: () => ({ currentUser: mocks.user }) }));
vi.mock("./LibraryContext", () => ({ useLibrary: () => ({ loading: false }) }));
vi.mock("./NotificationContext", () => ({ useNotifications: () => ({ notify: mocks.notify }) }));
vi.mock("../services/healthService", () => ({
  getHealth: vi.fn(() => Promise.resolve({ apiVersion: 12, capabilities: ["radio"] })),
}));
vi.mock("../services/playbackService", () => ({ getPlaybackState: vi.fn(() => Promise.resolve(mocks.saved)) }));
vi.mock("../services/tracksService", () => ({ getTracksByIds: (ids) => mocks.tracksById(ids) }));
vi.mock("../services/playlistsService", () => ({
  isTrackLiked: vi.fn(() => Promise.resolve(false)),
  likeTrack: vi.fn(),
  unlikeTrack: vi.fn(),
}));
vi.mock("../services/radioService", async (importOriginal) => ({ ...(await importOriginal()), ...mocks.radio }));

import { PlayerProvider } from "./PlayerProvider";
import { usePlayer } from "./PlayerContext";

let api = null;

function Probe() {
  // The test drives the provider through its context; a module variable is
  // the plainest handle for that.
  // eslint-disable-next-line react-hooks/globals
  api = usePlayer();
  return (
    <>
      <audio data-testid="audio" {...api.audioProps} />
      <output data-testid="queue">{api.queue.map((track) => track.id).join(",")}</output>
      <output data-testid="index">{api.queueIndex}</output>
      <output data-testid="station">{api.radioStation?.name || ""}</output>
    </>
  );
}

const station = { id: 4, name: "Fen radio", seed_type: "track", feedback: { more_track_ids: [], less_track_ids: [], less_artists: [] } };

function batch(ids, extra = {}) {
  return { station, tracks: ids.map((id) => ({ ...t(id), reason: `Close to Fen` })), thin: false, reach: null, ...extra };
}

async function mount() {
  render(
    <PlayerProvider>
      <Probe />
    </PlayerProvider>,
  );
  // The restore and the health check settle.
  await waitFor(() => expect(api.radioAvailable).toBe(true));
}

async function startTrackRadio(firstBatchIds) {
  mocks.radio.createStation.mockResolvedValueOnce(station);
  mocks.radio.getStationNext.mockResolvedValueOnce(batch(firstBatchIds));
  await act(async () => {
    await api.startRadio({ track: t(1, "Fen") });
  });
  await waitFor(() => expect(screen.getByTestId("queue").textContent).toBe([1, ...firstBatchIds].join(",")));
}

const queueIds = () => screen.getByTestId("queue").textContent.split(",").filter(Boolean).map(Number);

beforeEach(() => {
  vi.clearAllMocks();
  mocks.audioEl.ended = false;
  mocks.saved.queueTrackIds = [];
  mocks.saved.sourceType = "library";
  mocks.saved.sourceId = null;
  mocks.saved.currentTrackId = null;
  mocks.saved.queueIndex = -1;
  mocks.radio.getStationNext.mockReset();
  mocks.radio.getStationNext.mockResolvedValue(batch([]));
  mocks.radio.getStationLineup.mockResolvedValue({ station, tracks: [], resumable: false });
  mocks.radio.getStation.mockResolvedValue(station);
});

describe("a station in the browser", () => {
  it("starts from a track: the seed plays at once and the batch appends behind it", async () => {
    await mount();
    await startTrackRadio([2, 3, 4, 5, 6]);
    expect(api.radioStation.id).toBe(4);
    expect(api.radioReasons.get("1")).toBe("The track you started from");
    expect(api.radioReasons.get("2")).toBe("Close to Fen");
    expect(mocks.radio.getStationNext).toHaveBeenCalledWith(4, { excludeIds: [1] });
    // One batch at the start: the look-ahead rides on the one in flight.
    expect(mocks.radio.getStationNext).toHaveBeenCalledTimes(1);
  });

  it("asks for the next batch a few tracks before the end, excluding everything it holds", async () => {
    await mount();
    await startTrackRadio([2, 3, 4, 5, 6, 7, 8]);
    expect(mocks.radio.getStationNext).toHaveBeenCalledTimes(1);
    mocks.radio.getStationNext.mockResolvedValueOnce(batch([9, 10, 11]));
    act(() => api.jumpTo(4)); // three left: 6, 7, 8
    await waitFor(() => expect(mocks.radio.getStationNext).toHaveBeenCalledTimes(2));
    expect(mocks.radio.getStationNext.mock.calls[1][1].excludeIds).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    await waitFor(() => expect(queueIds()).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]));
    expect(screen.getByTestId("index").textContent).toBe("4");
  });

  it("continues the station on a skip from the last track instead of saying the list is over", async () => {
    await mount();
    await startTrackRadio([2]);
    // The look-ahead already asked once the queue was short; the skip rides
    // on that, or asks itself.
    mocks.radio.getStationNext.mockResolvedValue(batch([3, 4]));
    act(() => api.jumpTo(1));
    await act(async () => {
      api.next();
    });
    await waitFor(() => expect(Number(screen.getByTestId("index").textContent)).toBe(2));
    expect(queueIds().slice(0, 3)).toEqual([1, 2, 3]);
    expect(mocks.notify).not.toHaveBeenCalledWith("That was the last track in the list.");
  });

  it("asks the station for more when the last track ends, and plays on", async () => {
    await mount();
    await startTrackRadio([2]);
    mocks.radio.getStationNext.mockResolvedValue(batch([3]));
    act(() => api.jumpTo(1));
    mocks.audioEl.ended = true;
    await act(async () => {
      fireEvent.ended(screen.getByTestId("audio"));
    });
    await waitFor(() => expect(Number(screen.getByTestId("index").textContent)).toBe(2));
    expect(api.isPlaying).toBe(true);
  });

  it("reports a play once the track is heard — not on a reload, and once per track", async () => {
    mocks.saved.queueTrackIds = [1, 2, 3];
    mocks.saved.currentTrackId = 1;
    mocks.saved.queueIndex = 0;
    mocks.saved.sourceType = "radio";
    mocks.saved.sourceId = 4;
    mocks.tracksById.mockResolvedValue([t(1), t(2), t(3)]);
    mocks.radio.getStationLineup.mockResolvedValue({
      station,
      tracks: [{ ...t(1), reason: "The track you started from" }, { ...t(2), reason: "Close to Fen" }],
      resumable: true,
    });
    await mount();
    await waitFor(() => expect(screen.getByTestId("station").textContent).toBe("Fen radio"));
    expect(mocks.radio.reportStationPlays).not.toHaveBeenCalled();
    // The reasons come back with the lineup.
    await waitFor(() => expect(api.radioReasons.get("2")).toBe("Close to Fen"));

    fireEvent.play(screen.getByTestId("audio"));
    fireEvent.play(screen.getByTestId("audio"));
    expect(mocks.radio.reportStationPlays).toHaveBeenCalledTimes(1);
    expect(mocks.radio.reportStationPlays).toHaveBeenCalledWith(4, [1]);
  });

  it("replaces what is up next on Fresh batch", async () => {
    await mount();
    await startTrackRadio([2, 3, 4, 5, 6, 7]);
    act(() => api.jumpTo(1));
    mocks.radio.getStationNext.mockResolvedValueOnce(batch([20, 21]));
    await act(async () => {
      await api.fetchStationBatch();
    });
    expect(queueIds()).toEqual([1, 2, 20, 21]);
    // Only what has played and what is playing is held out: up next is let go.
    expect(mocks.radio.getStationNext).toHaveBeenCalledWith(4, { excludeIds: [1, 2] });
  });

  it("takes a track out of the queue when the listener says not this one, and tells the server", async () => {
    await mount();
    await startTrackRadio([2, 3, 4, 5, 6, 7]);
    mocks.radio.giveStationFeedback.mockResolvedValueOnce({ more_track_ids: [], less_track_ids: [4], less_artists: [] });
    await act(async () => {
      await api.giveStationFeedback(t(4), "less");
    });
    expect(mocks.radio.giveStationFeedback).toHaveBeenCalledWith(4, 4, "less");
    expect(queueIds()).toEqual([1, 2, 3, 5, 6, 7]);
    expect(api.radioStation.feedback.less_track_ids).toEqual([4]);

    mocks.radio.giveStationFeedback.mockResolvedValueOnce({ more_track_ids: [], less_track_ids: [4], less_artists: ["Someone"] });
    await act(async () => {
      await api.giveStationFeedback(t(5, "Someone"), "less_artist");
    });
    expect(queueIds()).toEqual([1]);
  });

  it("stops the station: the queue stays, nothing more is asked for", async () => {
    await mount();
    await startTrackRadio([2, 3, 4, 5, 6, 7]);
    act(() => api.stopStation());
    expect(screen.getByTestId("station").textContent).toBe("");
    expect(queueIds()).toEqual([1, 2, 3, 4, 5, 6, 7]);
    const asked = mocks.radio.getStationNext.mock.calls.length;
    act(() => api.jumpTo(6));
    await act(async () => {
      api.next();
    });
    expect(mocks.radio.getStationNext).toHaveBeenCalledTimes(asked);
    expect(mocks.notify).toHaveBeenCalledWith("That was the last track in the list.");
  });

  it("lets a station go when its seed has left the library", async () => {
    await mount();
    await startTrackRadio([2, 3, 4, 5, 6, 7]);
    mocks.radio.getStationNext.mockRejectedValueOnce(Object.assign(new Error("gone"), { status: 410 }));
    await act(async () => {
      await api.fetchStationBatch();
    });
    expect(mocks.notify).toHaveBeenCalledWith(expect.stringContaining("no longer in your library"));
    expect(screen.getByTestId("station").textContent).toBe("");
  });

  it("says once per station when a batch had to reach wider", async () => {
    await mount();
    mocks.radio.createStation.mockResolvedValueOnce(station);
    mocks.radio.getStationNext.mockResolvedValueOnce(batch([2, 3], { thin: true, reach: "listener" }));
    await act(async () => {
      await api.startRadio({ track: t(1, "Fen") });
    });
    await waitFor(() => expect(mocks.notify).toHaveBeenCalledWith(expect.stringContaining("what you play most")));
    const notices = mocks.notify.mock.calls.length;
    mocks.radio.getStationNext.mockResolvedValue(batch([8, 9], { thin: true, reach: "listener" }));
    await act(async () => {
      await api.fetchStationBatch();
    });
    expect(queueIds()).toContain(8);
    expect(mocks.notify.mock.calls.length).toBe(notices);
  });
});
