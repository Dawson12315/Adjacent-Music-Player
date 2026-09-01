import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useListeningEvents } from "./useListeningEvents";
import * as listeningService from "../services/listeningService";

const TRACK = { id: 42, title: "Test" };

function setup() {
  return renderHook(() =>
    useListeningEvents({
      getPosition: () => 12,
      getDuration: () => 180,
      getSource: () => ({ source_type: "playlist", source_id: 7 }),
    }),
  );
}

describe("useListeningEvents", () => {
  beforeEach(() => {
    vi.spyOn(listeningService, "recordPlayStart").mockResolvedValue({});
    vi.spyOn(listeningService, "recordSkip").mockResolvedValue({});
    vi.spyOn(listeningService, "recordPlayComplete").mockResolvedValue({});
    vi.spyOn(listeningService, "recordLike").mockResolvedValue({});
    vi.spyOn(listeningService, "recordUnlike").mockResolvedValue({});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends the playback source and position with the event", async () => {
    const { result } = setup();

    await act(async () => {
      result.current.resetForTrack(TRACK);
      await result.current.playStarted(TRACK);
    });

    expect(listeningService.recordPlayStart).toHaveBeenCalledWith(
      42,
      expect.objectContaining({
        sourceType: "playlist",
        sourceId: 7,
        positionSeconds: 12,
        durationSeconds: 180,
        sessionId: expect.stringContaining("session-"),
      }),
    );
  });

  it("records one play start per track no matter how often play fires", async () => {
    const { result } = setup();

    await act(async () => {
      result.current.resetForTrack(TRACK);
      await result.current.playStarted(TRACK);
      await result.current.playStarted(TRACK);
      await result.current.playStarted(TRACK);
    });

    expect(listeningService.recordPlayStart).toHaveBeenCalledTimes(1);
  });

  it("records a play start again once the track changes", async () => {
    const { result } = setup();
    const other = { id: 43, title: "Other" };

    await act(async () => {
      result.current.resetForTrack(TRACK);
      await result.current.playStarted(TRACK);
      result.current.resetForTrack(other);
      await result.current.playStarted(other);
    });

    expect(listeningService.recordPlayStart).toHaveBeenCalledTimes(2);
  });

  it("records at most one skip per track", async () => {
    const { result } = setup();

    await act(async () => {
      result.current.resetForTrack(TRACK);
      await result.current.skipped(TRACK);
      await result.current.skipped(TRACK);
    });

    expect(listeningService.recordSkip).toHaveBeenCalledTimes(1);
  });

  it("records at most one completion per track, at the full duration", async () => {
    const { result } = setup();

    await act(async () => {
      result.current.resetForTrack(TRACK);
      await result.current.completed(TRACK);
      await result.current.completed(TRACK);
    });

    expect(listeningService.recordPlayComplete).toHaveBeenCalledTimes(1);
    expect(listeningService.recordPlayComplete).toHaveBeenCalledWith(
      42,
      expect.objectContaining({ positionSeconds: 180, durationSeconds: 180 }),
    );
  });

  it("gives each track its own session id", async () => {
    const { result } = setup();
    const other = { id: 43, title: "Other" };

    await act(async () => {
      result.current.resetForTrack(TRACK);
      await result.current.playStarted(TRACK);
      result.current.resetForTrack(other);
      await result.current.playStarted(other);
    });

    const [[, first], [, second]] = listeningService.recordPlayStart.mock.calls;

    expect(first.sessionId).not.toBe(second.sessionId);
  });

  it("never lets a failed analytics write escape", async () => {
    listeningService.recordPlayStart.mockRejectedValue(new Error("network down"));
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { result } = setup();

    await act(async () => {
      result.current.resetForTrack(TRACK);
      await expect(result.current.playStarted(TRACK)).resolves.toBeUndefined();
    });
  });

  it("ignores calls with no track", async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.playStarted(null);
      await result.current.skipped(null);
      await result.current.completed(null);
    });

    expect(listeningService.recordPlayStart).not.toHaveBeenCalled();
    expect(listeningService.recordSkip).not.toHaveBeenCalled();
    expect(listeningService.recordPlayComplete).not.toHaveBeenCalled();
  });

  it("routes like and unlike to their own endpoints", async () => {
    const { result } = setup();

    await act(async () => {
      result.current.resetForTrack(TRACK);
      await result.current.likeChanged(TRACK, true);
      await result.current.likeChanged(TRACK, false);
    });

    expect(listeningService.recordLike).toHaveBeenCalledTimes(1);
    expect(listeningService.recordUnlike).toHaveBeenCalledTimes(1);
  });
});
