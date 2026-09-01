import { useCallback, useRef } from "react";

import * as listeningService from "../services/listeningService";

function createSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Records play-start / skip / play-complete / like / unlike, with the dedupe rules that
 * keep one play from producing several events.
 *
 * Each of these is fire-and-forget: a failed analytics write must never interrupt
 * playback, so failures are logged and swallowed.
 *
 * One deliberate change from the previous version: it refetched the entire stats
 * overview after every event, including while the Insights screen was closed. Insights
 * now loads when it is opened and has its existing refresh control.
 */
export function useListeningEvents({ getPosition, getDuration, getSource }) {
  const sessionIdRef = useRef(null);
  const eventTrackIdRef = useRef(null);
  const sentPlayStartRef = useRef(false);
  const sentSkipRef = useRef(false);
  const sentCompleteRef = useRef(false);

  const payloadFor = useCallback(
    (overrides = {}) => {
      const source = getSource();

      return {
        sourceType: source.source_type,
        sourceId: source.source_id,
        positionSeconds: getPosition(),
        durationSeconds: getDuration(),
        sessionId: sessionIdRef.current,
        ...overrides,
      };
    },
    [getPosition, getDuration, getSource],
  );

  /** Start a fresh event session; called whenever the loaded track changes. */
  const resetForTrack = useCallback((track) => {
    eventTrackIdRef.current = track?.id ?? null;
    sessionIdRef.current = track ? createSessionId() : null;
    sentPlayStartRef.current = false;
    sentSkipRef.current = false;
    sentCompleteRef.current = false;
  }, []);

  const playStarted = useCallback(
    async (track) => {
      if (!track) return;

      if (sentPlayStartRef.current && eventTrackIdRef.current === track.id) {
        return;
      }

      if (!sessionIdRef.current || eventTrackIdRef.current !== track.id) {
        sessionIdRef.current = createSessionId();
      }

      eventTrackIdRef.current = track.id;
      sentPlayStartRef.current = true;
      sentSkipRef.current = false;
      sentCompleteRef.current = false;

      try {
        await listeningService.recordPlayStart(track.id, payloadFor());
      } catch (error) {
        console.error("Failed to record play start", error);
      }
    },
    [payloadFor],
  );

  const skipped = useCallback(
    async (track) => {
      if (!track || sentSkipRef.current) return;

      sentSkipRef.current = true;

      try {
        await listeningService.recordSkip(track.id, payloadFor());
      } catch (error) {
        console.error("Failed to record skip", error);
      }
    },
    [payloadFor],
  );

  const completed = useCallback(
    async (track) => {
      if (!track || sentCompleteRef.current) return;

      sentCompleteRef.current = true;
      const finalDuration = getDuration();

      try {
        await listeningService.recordPlayComplete(
          track.id,
          payloadFor({ positionSeconds: finalDuration, durationSeconds: finalDuration }),
        );
      } catch (error) {
        console.error("Failed to record play completion", error);
      }
    },
    [payloadFor, getDuration],
  );

  const likeChanged = useCallback(
    async (track, liked) => {
      if (!track) return;

      try {
        const record = liked ? listeningService.recordLike : listeningService.recordUnlike;
        await record(track.id, payloadFor());
      } catch (error) {
        console.error("Failed to record like state", error);
      }
    },
    [payloadFor],
  );

  return { resetForTrack, playStarted, skipped, completed, likeChanged };
}
