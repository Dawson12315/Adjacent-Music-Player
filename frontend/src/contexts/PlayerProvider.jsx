import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { PlayerContext, PlayerProgressContext } from "./PlayerContext";
import { useAuth } from "./AuthContext";
import { useLibrary } from "./LibraryContext";
import { useNotifications } from "./NotificationContext";
import { useAudioElement } from "../hooks/useAudioElement";
import { useLastfmScrobbler } from "../hooks/useLastfmScrobbler";
import { useListeningEvents } from "../hooks/useListeningEvents";
import { useMediaSession } from "../hooks/useMediaSession";
import { usePlaybackPersistence } from "../hooks/usePlaybackPersistence";
import { useHandoff } from "../hooks/useHandoff";
import { getHealth } from "../services/healthService";
import { getPlaybackState } from "../services/playbackService";
import { getTracksByIds } from "../services/tracksService";
import {
  createStation,
  deleteStation,
  getStation,
  getStationLineup,
  getStationNext,
  giveStationFeedback as postStationFeedback,
  reportStationPlays,
  takeBackStationFeedback,
} from "../services/radioService";
import {
  EXHAUSTED_STATION_NOTICE,
  RADIO_UNAVAILABLE_NOTICE,
  REFILL_AHEAD,
  STATION_GONE_NOTICE,
  announceStationsChanged,
  feedbackState,
  isRadioSource,
  radioAvailableFor,
  radioFeedbackAvailableFor,
  radioSource,
  reachNotice,
  reasonsByTrackId,
  stationBatchCandidates,
  stationSeedFor,
  stationSeedName,
} from "../features/player/radio";
import { interpolatedPosition } from "../services/handoffProtocol";
import * as playlistsService from "../services/playlistsService";
import { initialPlayerState, playerReducer } from "../features/player/playerReducer";

const DEFAULT_SOURCE = { source_type: "library", source_id: null };
// What a station's queue plays under once the station is stopped: the
// tracks stay, nothing more arrives.
const QUEUE_SOURCE = { source_type: "queue", source_id: null };
const NO_SERVER = { apiVersion: 0, capabilities: [] };
// How many unplayable tracks in a row a station skips past before it stops.
const MAX_SKIPPED_ERRORS = 3;

/**
 * The single owner of playback state.
 *
 * Everything that touches the player — the player bar, track rows, the queue panel, OS
 * media keys and Last.fm — goes through here, so there is one source of truth rather
 * than several components each holding a piece of it.
 */
export function PlayerProvider({ children }) {
  const { currentUser } = useAuth();
  const { loading: libraryLoading } = useLibrary();
  const { notify } = useNotifications();

  const [state, dispatch] = useReducer(playerReducer, initialPlayerState);
  const [isPlaying, setIsPlaying] = useState(false);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isQueueOpen, setIsQueueOpen] = useState(false);
  const [isLiked, setIsLiked] = useState(false);
  const [hasRestored, setHasRestored] = useState(false);
  // True after the browser refused to start the audio without a gesture —
  // after a hand-over to this tab, typically. The bar then asks for the tap.
  const [awaitingGesture, setAwaitingGesture] = useState(false);

  const { currentTrack, queue, queueIndex, isShuffle, isLoop } = state;
  const currentTrackId = currentTrack?.id ?? null;

  // The latest state for the asynchronous paths (a refill landing, a track
  // ending), which must not act on the queue a stale closure remembers.
  const stateRef = useRef(state);
  stateRef.current = state;

  // The context playback started from, captured at play time so an event fired after
  // navigating away still records where the track was actually played from.
  const sourceRef = useRef(DEFAULT_SOURCE);

  /* ---------- the server's radio ---------- */

  const [server, setServer] = useState(NO_SERVER);
  useEffect(() => {
    if (!currentUser) {
      setServer(NO_SERVER);
      return undefined;
    }
    let cancelled = false;
    getHealth()
      .then((health) => {
        if (!cancelled) setServer(health);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [currentUser]);
  const radioAvailable = radioAvailableFor(server);
  const radioFeedbackAvailable = radioFeedbackAvailableFor(server);

  /* ---------- the station playing now ---------- */

  // The station, why it chose each track (by track id, as a string), and
  // which queue tracks came from it — a track added to the queue by hand is
  // not the station's, and is not reported to it.
  const [radioStation, setRadioStation] = useState(null);
  const [radioReasons, setRadioReasons] = useState(() => new Map());
  const stationTrackIdsRef = useRef(new Set());
  // One "reaching wider" notice per station, not one per batch.
  const reachNoticedRef = useRef(null);
  // The refill in flight, so the end of the queue and the look-ahead share
  // one request; and the queue length the look-ahead last asked at.
  const refillRef = useRef(null);
  const refillAskedForRef = useRef(null);
  // The last (station, track) reported, so a pause and resume is one play.
  const reportedPlayRef = useRef(null);
  // Unplayable tracks skipped in a row on a station.
  const skippedErrorsRef = useRef(0);
  // Station look-ups can overlap (a restore and a take-over); the last wins.
  const stationSyncRef = useRef(0);

  const clearStation = useCallback(() => {
    // No new state when there is nothing to clear: this runs on every play.
    setRadioStation((previous) => (previous ? null : previous));
    setRadioReasons((previous) => (previous.size ? new Map() : previous));
    stationTrackIdsRef.current = new Set();
    refillRef.current = null;
    refillAskedForRef.current = null;
  }, []);

  /** The station a source names, looked up for the bar after a restore or a take-over. */
  const syncStationFromSource = useCallback(
    (source, queueTracks = []) => {
      const generation = ++stationSyncRef.current;
      if (!isRadioSource(source)) {
        clearStation();
        return;
      }
      // The queue the station handed out is the station's: its plays count.
      stationTrackIdsRef.current = new Set(queueTracks.map((track) => String(track?.id)).filter((id) => id !== "null"));
      getStation(source.source_id)
        .then((station) => {
          if (stationSyncRef.current !== generation) return;
          setRadioStation(station || null);
          // The reasons live in the session; the station's lineup has them
          // for what is still queued, so the page is not bare after a reload.
          return getStationLineup(source.source_id)
            .then((lineup) => {
              if (stationSyncRef.current !== generation) return;
              const reasons = reasonsByTrackId(lineup.tracks);
              if (reasons.size) setRadioReasons((previous) => new Map([...reasons, ...previous]));
            })
            .catch(() => {});
        })
        .catch((error) => {
          if (stationSyncRef.current !== generation) return;
          // Gone on the server: the queue plays on, as a queue.
          if (error?.status === 404 || error?.status === 410) {
            sourceRef.current = QUEUE_SOURCE;
            clearStation();
          }
        });
    },
    [clearStation],
  );

  /** The station stops: what is queued plays on, nothing more arrives. */
  const stopStation = useCallback(() => {
    if (isRadioSource(sourceRef.current)) sourceRef.current = QUEUE_SOURCE;
    clearStation();
  }, [clearStation]);

  /** A batch came back: its reasons, its tracks, and one notice if it reached wide. */
  const absorbBatch = useCallback(
    (batch, stationId) => {
      const reasons = reasonsByTrackId(batch.tracks);
      setRadioReasons((previous) => {
        const next = new Map(previous);
        reasons.forEach((reason, id) => next.set(id, reason));
        return next;
      });
      (batch.tracks || []).forEach((track) => {
        if (track?.id != null) stationTrackIdsRef.current.add(String(track.id));
      });
      if (batch.station) setRadioStation(batch.station);
      if (batch.thin && reachNoticedRef.current !== stationId) {
        reachNoticedRef.current = stationId;
        notify(reachNotice(batch.reach, stationSeedName(batch.station)));
      }
    },
    [notify],
  );

  /**
   * The station's next batch, behind what is queued — or, for "Fresh batch",
   * in place of what is up next. One request at a time; a request that
   * lands after the station has been left is dropped. Resolves to how many
   * tracks joined the queue.
   */
  const refillStation = useCallback(
    ({ replaceUpcoming = false } = {}) => {
      const source = sourceRef.current;
      if (!isRadioSource(source)) return Promise.resolve(0);
      if (refillRef.current && !replaceUpcoming) return refillRef.current;
      const stationId = source.source_id;
      const { queue: current, queueIndex: index } = stateRef.current;
      const held = replaceUpcoming ? current.slice(0, index + 1) : current;
      const heldIds = new Set(held.map((track) => track?.id).filter((id) => id != null));

      const run = (async () => {
        try {
          const batch = await getStationNext(stationId, { excludeIds: [...heldIds] });
          // Something else started in the meantime: not this queue's batch.
          if (!isRadioSource(sourceRef.current) || sourceRef.current.source_id !== stationId) return 0;
          const tracks = stationBatchCandidates(batch.tracks, { excludeIds: heldIds });
          absorbBatch(batch, stationId);
          if (!tracks.length) return 0;
          dispatch(replaceUpcoming ? { type: "REPLACE_UPCOMING", tracks } : { type: "APPEND_TRACKS", tracks });
          return tracks.length;
        } catch (error) {
          if (error?.status === 410 || error?.status === 404) {
            notify(STATION_GONE_NOTICE);
            stopStation();
            announceStationsChanged();
            return 0;
          }
          notify("Couldn't reach your server for the station's next tracks.");
          return 0;
        } finally {
          if (refillRef.current === run) refillRef.current = null;
        }
      })();
      if (!replaceUpcoming) refillRef.current = run;
      return run;
    },
    [absorbBatch, notify, stopStation],
  );

  // Who holds the music, for the error path below: the handoff hook mounts
  // further down, so it is read through a ref kept current each render.
  const holderNameRef = useRef(null);

  const handlePlaybackError = useCallback(
    (error) => {
      setIsPlaying(false);

      // Expected when a hand-over asks to resume without a user gesture: the
      // music is this tab's to play, it only needs the tap. Say so instead of
      // leaving a paused bar that looks like nothing happened.
      if (error.kind === "autoplay-blocked") {
        setAwaitingGesture(true);
        return;
      }
      // A stream refused because another device is playing surfaces as a
      // media error, and the generic text said the format was unsupported.
      if (error.kind === "media-error" && holderNameRef.current) {
        notify(`Playing on ${holderNameRef.current}. Press play here to bring it to this browser.`);
        return;
      }
      // A station's tracks are the server's choice, unvetted: one that will
      // not play is skipped, up to a few in a row, rather than ending the
      // station on it.
      if (error.kind === "media-error" && isRadioSource(sourceRef.current)) {
        const { queue: current, queueIndex: index, currentTrack: track } = stateRef.current;
        skippedErrorsRef.current += 1;
        if (skippedErrorsRef.current <= MAX_SKIPPED_ERRORS && index >= 0 && index < current.length - 1) {
          notify(`Skipped ${track?.title ? `"${track.title}"` : "a track"}: it couldn't be played.`);
          dispatch({ type: "NEXT" });
          setIsPlaying(true);
          return;
        }
      }
      notify(error.message);
    },
    [notify],
  );

  useEffect(() => {
    if (isPlaying) setAwaitingGesture(false);
  }, [isPlaying]);

  // The handoff hook mounts further down; its "is the lease known yet" is
  // read through a ref-backed state so the element can be told to wait.
  const [holdSource, setHoldSource] = useState(true);

  const audio = useAudioElement({
    track: currentTrack,
    isPlaying,
    volume,
    isMuted,
    onPlaybackError: handlePlaybackError,
    holdSource,
  });

  const { audioRef, currentTime, duration, seek, requestSeek, hasPendingSeek, hasSource } = audio;

  const getPosition = useCallback(() => audioRef.current?.currentTime ?? 0, [audioRef]);
  const getDuration = useCallback(() => audioRef.current?.duration || null, [audioRef]);
  const getSource = useCallback(() => sourceRef.current, []);

  const events = useListeningEvents({ getPosition, getDuration, getSource });
  const { resetForTrack } = events;

  useEffect(() => {
    resetForTrack(currentTrack);
    // Only the identity of the track matters here, not its metadata.
  }, [currentTrackId, resetForTrack]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---------- restore the saved session ---------- */

  useEffect(() => {
    if (!currentUser || libraryLoading || hasRestored) {
      return undefined;
    }

    let cancelled = false;

    async function restore() {
      try {
        const saved = await getPlaybackState();

        if (cancelled) return;

        /*
         * The queue is stored as bare track ids. The library is no longer held in memory,
         * so they are resolved in one request — in order, and capped, since a queue built
         * from "play everything" could otherwise be tens of thousands long.
         */
        const restoredQueue = saved.queueTrackIds.length
          ? await getTracksByIds(saved.queueTrackIds)
          : [];

        if (cancelled) return;

        // The saved index is the server's; the resolved list may be shorter
        // (a track cleaned up since) and the index must land inside it.
        const byId = saved.currentTrackId != null
          ? restoredQueue.findIndex((item) => item?.id === saved.currentTrackId)
          : -1;
        const restoredIndex =
          byId >= 0
            ? byId
            : Math.min(Math.max(0, Number(saved.queueIndex) || 0), Math.max(0, restoredQueue.length - 1));
        const restoredTrack =
          restoredQueue[restoredIndex] ??
          (saved.currentTrackId
            ? (await getTracksByIds([saved.currentTrackId]))[0] ?? null
            : null);

        if (cancelled) return;

        // What the queue was playing from comes back with it, so a station
        // is still a station after a reload: chip, page and refills intact.
        sourceRef.current = {
          source_type: saved.sourceType ?? DEFAULT_SOURCE.source_type,
          source_id: saved.sourceId ?? null,
        };
        syncStationFromSource(sourceRef.current, restoredQueue);

        dispatch({
          type: "RESTORE",
          queue: restoredQueue,
          queueIndex: restoredQueue.length ? restoredIndex : saved.queueIndex,
          currentTrack: restoredTrack,
          isShuffle: saved.isShuffle,
          isLoop: saved.isLoop,
        });

        if (restoredTrack && Number.isFinite(saved.currentTimeSeconds)) {
          requestSeek(saved.currentTimeSeconds, restoredTrack.id);
        }

        // Restored paused, whatever the session says. The saved "playing" is
        // another device's, or a previous tab's that a reload interrupted;
        // copying it here claimed the lease from the device actually playing
        // and then could not start, the browser refusing autoplay without a
        // gesture — phone silent, browser paused. Playing is an intent, and
        // the next tap supplies it.
      } catch (error) {
        console.error("Failed to restore playback state", error);
      } finally {
        if (!cancelled) {
          setHasRestored(true);
        }
      }
    }

    restore();

    return () => {
      cancelled = true;
    };
  }, [currentUser, libraryLoading, hasRestored, requestSeek, syncStationFromSource]);

  /* ---------- persistence ---------- */

  const queueTrackIds = useMemo(() => queue.map((track) => track.id), [queue]);

  // The source is read live at save time (it lives in a ref), so a station
  // started a moment ago is saved as one: see usePlaybackPersistence.
  const snapshot = useMemo(
    () => ({
      currentTrackId,
      queueIndex,
      isPlaying,
      isShuffle,
      isLoop,
      queueTrackIds,
    }),
    [currentTrackId, queueIndex, isPlaying, isShuffle, isLoop, queueTrackIds],
  );

  // The persistence hook itself is mounted after the handoff section below:
  // it is gated on the lease, and names this browser to the server.

  /* ---------- liked state for the current track ---------- */

  useEffect(() => {
    if (!currentUser || !currentTrackId) {
      return undefined;
    }

    const controller = new AbortController();

    playlistsService
      .isTrackLiked(currentTrackId, { signal: controller.signal })
      .then(setIsLiked)
      .catch((error) => {
        if (error.name !== "AbortError") {
          setIsLiked(false);
        }
      });

    return () => controller.abort();
  }, [currentUser, currentTrackId]);

  /* ---------- transport ---------- */

  // The handoff hook mounts below the transport, but every play goes through
  // its claim first: the lease moves to this browser before the audio element
  // asks for the stream, which the server refuses to a non-holder while
  // another device is playing. Awaited only when it is taking the music from
  // someone (one HTTP round trip); otherwise it is a frame on the wire.
  const handoffClaimRef = useRef(null);
  const claimBeforePlay = useCallback((overrides) => handoffClaimRef.current?.(overrides), []);
  // A take-over sets isPlaying without an intent of this tab's: the lease is
  // already here. The playing-edge claim below must not fire for it.
  const suppressEdgeClaimRef = useRef(false);

  const playTrack = useCallback(
    async (track, sourceTracks = [], source = DEFAULT_SOURCE) => {
      if (currentTrack && currentTrack.id !== track.id && !audioRef.current?.ended) {
        events.skipped(currentTrack);
      }

      // The source first: the claim snapshots it, and a claim that carried the
      // previous source told the server a station was a library queue.
      sourceRef.current = source;
      await claimBeforePlay({ trackId: track.id, position: 0, playing: true });
      // Anything but the station's own batches ends the station.
      if (!isRadioSource(source)) clearStation();
      dispatch({ type: "PLAY_TRACK", track, sourceTracks });
      setIsPlaying(true);
    },
    [currentTrack, events, audioRef, claimBeforePlay, clearStation],
  );

  const playTracks = useCallback(
    async (tracksToPlay, source = DEFAULT_SOURCE) => {
      if (tracksToPlay.length === 0) return;

      sourceRef.current = source;
      await claimBeforePlay({ trackId: tracksToPlay[0]?.id ?? null, position: 0, playing: true });
      if (!isRadioSource(source)) clearStation();
      dispatch({ type: "PLAY_TRACKS", tracks: tracksToPlay });
      setIsPlaying(true);
    },
    [claimBeforePlay, clearStation],
  );

  /** A station starts: its state is fresh, and the first batch is the queue. */
  const beginStation = useCallback(
    (station) => {
      clearStation();
      skippedErrorsRef.current = 0;
      setRadioStation(station);
    },
    [clearStation],
  );

  /**
   * Play a station from its first batch, in the station's order: track
   * radio opens with the seed, and the blend is the server's to decide.
   * Resolves to the station, or false — and says why.
   */
  const playStation = useCallback(
    async (station) => {
      if (!station?.id) return false;
      try {
        // Where the station was left, if it played in the last ten days: that
        // continues, from the track the listener got to, without asking the
        // recommender again. An older server has no lineup and answers 404.
        let batch = null;
        try {
          const lineup = await getStationLineup(station.id);
          if (lineup.resumable && lineup.tracks.length) batch = lineup;
        } catch (error) {
          if (error?.status === 410) throw error;
          batch = null;
        }
        if (!batch) batch = await getStationNext(station.id);
        const tracks = stationBatchCandidates(batch.tracks);
        if (!tracks.length) {
          notify("Nothing in your library to build that station from yet.");
          return false;
        }
        const played = batch.station || station;
        beginStation(played);
        absorbBatch(batch, station.id);
        await playTracks(tracks, radioSource(station.id));
        announceStationsChanged();
        return played;
      } catch (error) {
        if (error?.status === 410) {
          notify(STATION_GONE_NOTICE);
          announceStationsChanged();
        } else if (error?.status === 404) {
          notify("That station is gone.");
          announceStationsChanged();
        } else {
          notify(error?.message || "Couldn't reach your server to start the station.");
        }
        return false;
      }
    },
    [notify, playTracks, beginStation, absorbBatch],
  );

  /** "Fresh batch" on the station's page: what is up next is replaced. Resolves to how many arrived. */
  const fetchStationBatch = useCallback(async () => {
    const added = await refillStation({ replaceUpcoming: true });
    if (!added && isRadioSource(sourceRef.current)) notify(EXHAUSTED_STATION_NOTICE);
    return added;
  }, [refillStation, notify]);

  /** "Start radio" from a track menu, an album page or an artist page. */
  const startRadio = useCallback(
    async (seedFrom) => {
      const seed = stationSeedFor(seedFrom || {});
      if (!seed) return false;
      if (!radioAvailable) {
        notify(RADIO_UNAVAILABLE_NOTICE);
        return false;
      }
      try {
        const station = await createStation(seed);

        // Track radio opens with the seed, and the seed is in hand: it plays
        // now, and the rest of the batch extends the queue behind it when
        // the station answers, so the server's moment is not heard.
        if (seed.seed_type === "track" && seedFrom.track?.id) {
          const seedTrack = seedFrom.track;
          beginStation(station);
          setRadioReasons(new Map([[String(seedTrack.id), "The track you started from"]]));
          stationTrackIdsRef.current.add(String(seedTrack.id));
          // Asked for while the seed starts, not after. It is also the refill
          // in flight: a queue of one track is "near its end", and the
          // look-ahead would otherwise ask for a second batch on top.
          const batchPromise = getStationNext(station.id, { excludeIds: [seedTrack.id] });
          const inFlight = batchPromise.then(() => 0, () => 0);
          refillRef.current = inFlight;
          try {
            await playTracks([seedTrack], radioSource(station.id));
            const batch = await batchPromise;
            if (!isRadioSource(sourceRef.current) || sourceRef.current.source_id !== station.id) return station;
            const rest = stationBatchCandidates(batch.tracks, { excludeIds: new Set([seedTrack.id]) });
            absorbBatch(batch, station.id);
            if (rest.length) dispatch({ type: "APPEND_TRACKS", tracks: rest });
          } finally {
            if (refillRef.current === inFlight) refillRef.current = null;
          }
          announceStationsChanged();
          return station;
        }

        return await playStation(station);
      } catch (error) {
        notify(
          error?.status === 404
            ? "This server has no radio yet, or nothing to build that station from."
            : error?.message || "Couldn't start radio.",
        );
        return false;
      }
    },
    [notify, playStation, playTracks, radioAvailable, beginStation, absorbBatch],
  );

  /** A station is deleted, here and on the server. */
  const deleteStationById = useCallback(
    async (stationId) => {
      try {
        await deleteStation(stationId);
      } catch (error) {
        if (error?.status !== 404) {
          notify(error?.message || "Couldn't remove that station.");
          return false;
        }
      }
      if (isRadioSource(sourceRef.current) && sourceRef.current.source_id === stationId) stopStation();
      announceStationsChanged();
      return true;
    },
    [notify, stopStation],
  );

  const togglePlay = useCallback(async () => {
    if (!currentTrack) return;
    if (!isPlaying) await claimBeforePlay({ playing: true });
    setIsPlaying((previous) => !previous);
  }, [currentTrack, isPlaying, claimBeforePlay]);

  const play = useCallback(async () => {
    if (!currentTrack) return;
    await claimBeforePlay({ playing: true });
    setIsPlaying(true);
  }, [currentTrack, claimBeforePlay]);

  const pause = useCallback(() => setIsPlaying(false), []);

  /** Past the end of the queue on a station: the next batch, then on to it. */
  const advancePastEnd = useCallback(
    async ({ keepPlaying }) => {
      // The count the refill reports is the truth about the queue: the
      // append it dispatched may not have rendered yet when this resumes,
      // so the ref alone could still say the queue ends here.
      const added = await refillStation();
      const { queue: current, queueIndex: index } = stateRef.current;
      if (added > 0 || (index >= 0 && index < current.length - 1)) {
        dispatch({ type: "NEXT" });
        if (keepPlaying) setIsPlaying(true);
        return true;
      }
      if (isRadioSource(sourceRef.current)) notify(EXHAUSTED_STATION_NOTICE);
      setIsPlaying(false);
      return false;
    },
    [refillStation, notify],
  );

  const next = useCallback(() => {
    if (queue.length > 0 && queueIndex >= queue.length - 1) {
      // A station does not end at the end of a batch: it is asked for more.
      if (isRadioSource(sourceRef.current)) {
        if (currentTrack && !audioRef.current?.ended) events.skipped(currentTrack);
        advancePastEnd({ keepPlaying: isPlaying });
        return;
      }
      // The reducer ignores Next at the end of the list; say so, or a Next that
      // does nothing reads as a player that has stopped working.
      notify("That was the last track in the list.");
      return;
    }

    if (currentTrack && !audioRef.current?.ended) {
      events.skipped(currentTrack);
    }

    dispatch({ type: "NEXT" });
  }, [currentTrack, events, audioRef, queue.length, queueIndex, notify, advancePastEnd, isPlaying]);

  const previous = useCallback(() => {
    const position = audioRef.current?.currentTime ?? 0;

    if (currentTrack && position > 0 && !audioRef.current?.ended) {
      events.skipped(currentTrack);
    }

    // Past five seconds, "previous" restarts the track instead of stepping back.
    if (position > 5 || queueIndex <= 0) {
      seek(0);
      return;
    }

    dispatch({ type: "PREVIOUS" });
  }, [currentTrack, events, audioRef, queueIndex, seek]);

  const jumpTo = useCallback((index) => dispatch({ type: "JUMP_TO", index }), []);
  const addToQueue = useCallback((track) => dispatch({ type: "ADD_TO_QUEUE", track }), []);
  const removeFromQueue = useCallback(
    (index) => dispatch({ type: "REMOVE_AT", index }),
    [],
  );
  const toggleShuffle = useCallback(() => dispatch({ type: "TOGGLE_SHUFFLE" }), []);

  /** The list the queue came from has more now; the reducer decides whether it applies. */
  const extendQueue = useCallback((tracks) => dispatch({ type: "EXTEND_QUEUE", tracks }), []);
  const toggleLoop = useCallback(() => dispatch({ type: "TOGGLE_LOOP" }), []);
  const replaceTrack = useCallback((track) => dispatch({ type: "REPLACE_TRACK", track }), []);

  const clearPlayback = useCallback(() => {
    stopStation();
    sourceRef.current = DEFAULT_SOURCE;
    dispatch({ type: "CLEAR" });
    setIsPlaying(false);
  }, [stopStation]);

  /**
   * What the listener says about a track on the playing station: "more"
   * (it joins the seeds), "less" (it leaves the station, and the queue),
   * "less_artist" (the artist leaves the neighbours, and the queue). Said
   * twice, it is taken back. Resolves to whether it was saved.
   */
  const giveStationFeedback = useCallback(
    async (track, kind) => {
      const source = sourceRef.current;
      const stationId = radioStation?.id ?? (isRadioSource(source) ? source.source_id : null);
      if (!stationId || track?.id == null) return false;
      if (!radioFeedbackAvailable) {
        notify(RADIO_UNAVAILABLE_NOTICE);
        return false;
      }
      const said = feedbackState(radioStation?.feedback, track);
      const takingBack = (kind === "more" && said.more) || (kind === "less" && said.less) || (kind === "less_artist" && said.lessArtist);
      try {
        const feedback = takingBack
          ? await takeBackStationFeedback(stationId, track.id, kind)
          : await postStationFeedback(stationId, track.id, kind);
        setRadioStation((previous) => (previous && previous.id === stationId ? { ...previous, feedback } : previous));
        if (takingBack) return true;
        if (kind === "less") {
          dispatch({ type: "REMOVE_UPCOMING", trackIds: [track.id] });
          if (stateRef.current.currentTrack?.id === track.id) next();
          notify(`"${track.title}" won't play on this station again.`);
        } else if (kind === "less_artist") {
          dispatch({ type: "REMOVE_UPCOMING", artists: [track.artist] });
          if (track.artist && stateRef.current.currentTrack?.artist === track.artist) next();
          notify(`Less of ${track.artist} on this station.`);
        } else {
          notify(`More like "${track.title}" on this station.`);
        }
        return true;
      } catch (error) {
        notify(error?.status === 409 ? "That artist is the station." : error?.message || "Couldn't save that.");
        return false;
      }
    },
    [radioStation, radioFeedbackAvailable, notify, next],
  );

  const toggleMute = useCallback(() => setIsMuted((previous) => !previous), []);

  const changeVolume = useCallback((value) => {
    setVolume(value);
    setIsMuted(value === 0);
  }, []);

  const toggleQueue = useCallback(() => setIsQueueOpen((previous) => !previous), []);

  const toggleLike = useCallback(async () => {
    if (!currentTrack) return;

    const wasLiked = isLiked;

    // Optimistic: the heart flips instantly and reverts only if the server
    // disagrees. The round trip can be slow (a running library scan holds the
    // database's write lock in bursts) and the icon must not wait on it.
    setIsLiked(!wasLiked);

    try {
      const liked = wasLiked
        ? await playlistsService.unlikeTrack(currentTrack.id)
        : await playlistsService.likeTrack(currentTrack.id);

      setIsLiked(liked);
      events.likeChanged(currentTrack, !wasLiked);
    } catch (error) {
      setIsLiked(wasLiked);
      notify(error.message || "Could not update your liked songs.");
    }
  }, [currentTrack, isLiked, events, notify]);

  /* ---------- audio element wiring ---------- */

  const handleEnded = useCallback(() => {
    // Recorded, not awaited: the gap between tracks was the length of this
    // request, and a server holding its write lock stalled the queue.
    if (currentTrack) {
      Promise.resolve(events.completed(currentTrack)).catch(() => {});
    }

    if (isLoop) {
      events.resetForTrack(currentTrack);
      seek(0);
      // The element paused itself at the end; isPlaying never changed, so
      // the play effect will not run. Start it again here.
      audioRef.current?.play?.()?.catch?.(() => {});
      setIsPlaying(true);
      return;
    }

    // Stop at the end of the queue rather than wrapping around, unless a
    // station is playing: then the station is asked for its next batch —
    // usually already in hand, asked for a few tracks ago.
    if (queueIndex === -1 || queueIndex >= queue.length - 1) {
      if (isRadioSource(sourceRef.current)) {
        advancePastEnd({ keepPlaying: true });
        return;
      }
      setIsPlaying(false);
      return;
    }

    dispatch({ type: "NEXT" });
    setIsPlaying(true);
  }, [currentTrack, events, isLoop, queueIndex, queue, seek, audioRef, advancePastEnd]);

  // The element fires `pause` before `ended` at the end of a track. Taking
  // that pause as the user's flipped isPlaying false and back, which sent a
  // full claim (the whole queue) to every device on every advance and showed
  // the remotes a flash of "paused" between tracks.
  const handlePauseEvent = useCallback(() => {
    if (audioRef.current?.ended) return;
    setIsPlaying(false);
  }, [audioRef]);

  const handlePlayEvent = useCallback(() => {
    setIsPlaying(true);
    skippedErrorsRef.current = 0;

    if (currentTrack) {
      events.playStarted(currentTrack);
      // The station remembers what it played, so the next batch moves on:
      // reported when the track is actually heard, once, and only for the
      // station's own tracks — not on a reload that restores a station
      // paused, and not for a track added to the queue by hand.
      const source = sourceRef.current;
      if (isRadioSource(source) && stationTrackIdsRef.current.has(String(currentTrack.id))) {
        const key = `${source.source_id}:${currentTrack.id}`;
        if (reportedPlayRef.current !== key) {
          reportedPlayRef.current = key;
          reportStationPlays(source.source_id, [currentTrack.id]).catch(() => {});
        }
      }
    }
  }, [currentTrack, events]);

  const audioProps = useMemo(
    () => ({
      ref: audioRef,
      onPlay: handlePlayEvent,
      onPause: handlePauseEvent,
      onEnded: handleEnded,
      onTimeUpdate: audio.handleTimeUpdate,
      onLoadedMetadata: audio.handleLoadedMetadata,
      onError: audio.handleError,
    }),
    [
      audioRef,
      handlePlayEvent,
      handlePauseEvent,
      handleEnded,
      audio.handleTimeUpdate,
      audio.handleLoadedMetadata,
      audio.handleError,
    ],
  );

  useMediaSession({
    track: currentTrack,
    isPlaying,
    onPlay: play,
    onPause: pause,
    onNext: next,
    onPrevious: previous,
  });

  useLastfmScrobbler({
    track: currentTrack,
    isPlaying,
    enabled: Boolean(currentUser),
  });

  const upcomingQueue = useMemo(() => queue.slice(queueIndex + 1), [queue, queueIndex]);

  /* ---------- device handoff ---------- */

  const handoffStateSnapshot = useCallback(
    () => ({
      trackId: currentTrackId,
      queue: queueTrackIds,
      index: queueIndex,
      position: getPosition(),
      // "Playing" to the other devices means audio is actually attached and
      // rolling here. An element with no stream reported itself playing,
      // took the lease, and silenced every other device for nothing.
      playing: isPlaying && hasSource(),
      shuffle: isShuffle,
      loop: isLoop,
      source: getSource(),
    }),
    [currentTrackId, queueTrackIds, queueIndex, getPosition, isPlaying, isShuffle, isLoop, getSource, hasSource],
  );

  const handoffPauseForRemote = useCallback(() => setIsPlaying(false), []);

  // This browser was handed the music: load the queue, seek, play or hold.
  const handoffTakeOver = useCallback(
    async (serverState) => {
      if (!serverState) return;
      try {
        const ids = Array.isArray(serverState.queue_track_ids) ? serverState.queue_track_ids : [];
        const tracks = ids.length ? await getTracksByIds(ids) : [];
        const idx =
          Number.isFinite(serverState.queue_index) && serverState.queue_index >= 0 ? serverState.queue_index : 0;
        // By id first: the resolved list drops duplicates, so the index can
        // point past the track the other device was on.
        const currentId = serverState.current_track_id ?? null;
        const startTrack =
          (currentId != null ? tracks.find((item) => item?.id === currentId) : null) ||
          tracks[idx] ||
          (currentId != null ? (await getTracksByIds([currentId]))[0] : null) ||
          tracks[0] ||
          null;
        if (!startTrack) return;

        sourceRef.current = { source_type: serverState.source_type ?? null, source_id: serverState.source_id ?? null };
        syncStationFromSource(sourceRef.current, tracks);
        dispatch({
          type: "RESTORE",
          queue: tracks,
          queueIndex: idx,
          currentTrack: startTrack,
          isShuffle: Boolean(serverState.is_shuffle),
          isLoop: Boolean(serverState.is_loop),
        });
        // Where the other device is *now*: its last report plus the time
        // since, while it was playing. Reports are five seconds apart, and
        // a take-over used to land up to that far behind.
        const reportedAtMs = serverState.reported_at ? Date.parse(serverState.reported_at) : NaN;
        const position = interpolatedPosition({
          position: Number(serverState.current_time_seconds) || 0,
          playing: Boolean(serverState.is_playing),
          reportedAtMs: Number.isFinite(reportedAtMs) ? reportedAtMs : null,
        });
        if (position > 0) requestSeek(position, startTrack.id);
        // The browser may refuse autoplay without a gesture; the bar then
        // asks for the tap and the lease stays here, paused, with the pause
        // reported so the others are not refused a stream in the meantime.
        if (serverState.is_playing) suppressEdgeClaimRef.current = true;
        setIsPlaying(Boolean(serverState.is_playing));
      } catch (error) {
        console.error("Failed to take over playback", error);
      }
    },
    [dispatch, requestSeek, syncStationFromSource],
  );

  // A remote asked this (the holding) browser to do something.
  const handoffRunCommand = useCallback(
    (action, args = {}) => {
      switch (action) {
        case "play":
          if (currentTrack) setIsPlaying(true);
          break;
        case "pause":
          setIsPlaying(false);
          break;
        case "next":
          next();
          break;
        case "previous":
          previous();
          break;
        case "seek": {
          // A seek from another device is for the track it was looking at,
          // not for whatever this browser has moved on to since.
          const forTrack = args?.trackId;
          if (forTrack != null && currentTrackId != null && String(forTrack) !== String(currentTrackId)) break;
          if (Number.isFinite(Number(args?.position))) seek(Number(args.position));
          break;
        }
        case "shuffle":
          if ((args?.mode === "on") !== isShuffle) toggleShuffle();
          break;
        case "repeat":
          if ((args?.mode && args.mode !== "off") !== isLoop) toggleLoop();
          break;
        case "volume":
          if (Number.isFinite(Number(args?.volume))) changeVolume(Number(args.volume));
          break;
        default:
          break;
      }
    },
    [currentTrack, currentTrackId, next, previous, seek, isShuffle, toggleShuffle, isLoop, toggleLoop, changeVolume],
  );

  const handoffOnError = useCallback((error) => notify(error.message), [notify]);

  const handoff = useHandoff({
    currentUser,
    getStateSnapshot: handoffStateSnapshot,
    pauseForRemote: handoffPauseForRemote,
    takeOver: handoffTakeOver,
    runCommand: handoffRunCommand,
    onError: handoffOnError,
  });

  // A holder that has gone quiet is not a device to drive; the controls work
  // this browser, which is the only thing they could usefully do.
  const handoffPlayingElsewhere =
    handoff.available && !handoff.isActiveHere && Boolean(handoff.activeDeviceId) && !handoff.stale;
  holderNameRef.current = handoffPlayingElsewhere ? handoff.activeName || "another device" : null;
  const followingRef = useRef(false);
  followingRef.current = handoffPlayingElsewhere;

  // A station is asked for more a few tracks before the queue runs out, so
  // the next batch is in hand when the last track ends — in this browser,
  // not in a tab that is only following the device that holds the music.
  useEffect(() => {
    if (!isRadioSource(sourceRef.current) || followingRef.current) return;
    if (queueIndex < 0 || !queue.length) return;
    if (queue.length - 1 - queueIndex > REFILL_AHEAD) return;
    const key = `${sourceRef.current.source_id}:${queue.length}`;
    if (refillAskedForRef.current === key) return;
    refillAskedForRef.current = key;
    refillStation();
  }, [queue, queueIndex, refillStation]);

  const { claim: handoffClaim, reportPosition: handoffReport, isActiveHere: handoffActiveHere, leaseKnown } = handoff;
  handoffClaimRef.current = handoffClaim;

  // The audio element may load a stream once the lease is known (or the
  // hook gave up waiting), and never while another device is playing: the
  // server refuses that stream, and the element then sits in an error state.
  useEffect(() => {
    setHoldSource(!leaseKnown || handoffPlayingElsewhere);
  }, [leaseKnown, handoffPlayingElsewhere]);

  // The transport claims on the way in (above). This is the second line: once
  // the browser really is playing, the full state goes up again with the
  // queue as built. A false->true of the local isPlaying is this browser
  // becoming the one playing; a remote's playing flag is handoff.remote.
  const wasPlayingForHandoffRef = useRef(false);
  useEffect(() => {
    if (isPlaying && !wasPlayingForHandoffRef.current) {
      if (suppressEdgeClaimRef.current) suppressEdgeClaimRef.current = false;
      else handoffClaim();
    }
    wasPlayingForHandoffRef.current = isPlaying;
  }, [isPlaying, handoffClaim]);

  /* ---------- following the holder ---------- */

  // The track the other device is on, so the bar shows what is actually
  // playing rather than whatever this tab last had loaded.
  const remoteTrackId = handoffPlayingElsewhere ? (handoff.remote?.trackId ?? null) : null;
  const [remoteTrack, setRemoteTrack] = useState(null);
  useEffect(() => {
    if (remoteTrackId == null) {
      setRemoteTrack(null);
      return undefined;
    }
    if (remoteTrackId === currentTrackId) {
      setRemoteTrack(currentTrack);
      return undefined;
    }
    let cancelled = false;
    getTracksByIds([remoteTrackId])
      .then((tracks) => {
        if (!cancelled) setRemoteTrack(tracks[0] || null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [remoteTrackId, currentTrackId, currentTrack]);

  // A once-a-second clock while the remote plays, so its progress bar moves
  // between reports. Nothing else re-renders on it: only the progress context.
  const remotePlaying = Boolean(handoffPlayingElsewhere && handoff.remote?.playing);
  const [remoteNowMs, setRemoteNowMs] = useState(() => Date.now());
  useEffect(() => {
    if (!remotePlaying) return undefined;
    setRemoteNowMs(Date.now());
    const id = setInterval(() => setRemoteNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [remotePlaying]);

  const { sendCommand: handoffSendCommand } = handoff;
  const remoteSeek = useCallback(
    (seconds) => {
      if (!Number.isFinite(seconds)) return;
      // Named for the track the bar is showing, so the holder can ignore it
      // if it has moved on by the time it arrives.
      handoffSendCommand("seek", { position: Math.max(0, Math.floor(seconds)), trackId: remoteTrackId ?? undefined });
    },
    [handoffSendCommand, remoteTrackId],
  );

  // Report position to the other devices every few seconds while holding,
  // and at once when the music pauses, so a remote is not shown playing for
  // up to five seconds after.
  useEffect(() => {
    if (!handoffActiveHere) return undefined;
    if (!isPlaying) {
      handoffReport({ playing: false });
      return undefined;
    }
    // At once on the way in too, so the others see the music start rather
    // than a pause that lasts until the first five-second tick.
    handoffReport();
    const id = setInterval(() => handoffReport(), 5000);
    return () => clearInterval(id);
  }, [handoffActiveHere, isPlaying, handoffReport]);

  // The resume point on the server. Only while this browser holds the lease
  // or nobody does: a remote tab following another device must not overwrite
  // what that device reports. The device id lets the server say so (409)
  // rather than take the write.
  // The position is not worth writing while a restored one is still waiting
  // for the track's metadata: it read as 0 and overwrote the server's.
  const getPersistedPosition = useCallback(
    () => (hasPendingSeek() ? null : getPosition()),
    [hasPendingSeek, getPosition],
  );

  usePlaybackPersistence({
    enabled: Boolean(currentUser) && hasRestored && !handoffPlayingElsewhere,
    snapshot,
    getCurrentTime: getPersistedPosition,
    getSource,
    deviceId: handoff.me?.deviceId ?? null,
  });

  const radioReason = radioReasons.get(String(currentTrackId)) || null;

  const value = useMemo(
    () => ({
      currentTrack,
      queue,
      upcomingQueue,
      queueIndex,
      isPlaying,
      isShuffle,
      isLoop,
      volume,
      isMuted,
      isQueueOpen,
      isLiked,
      audioProps,
      playTrack,
      playTracks,
      extendQueue,
      togglePlay,
      play,
      pause,
      next,
      previous,
      jumpTo,
      addToQueue,
      removeFromQueue,
      toggleShuffle,
      toggleLoop,
      toggleMute,
      changeVolume,
      toggleQueue,
      toggleLike,
      clearPlayback,
      replaceTrack,
      handoff,
      handoffPlayingElsewhere,
      remoteTrack,
      awaitingGesture,
      radioAvailable,
      radioFeedbackAvailable,
      radioStation,
      radioReason,
      radioReasons,
      startRadio,
      playStation,
      fetchStationBatch,
      stopStation,
      deleteStationById,
      giveStationFeedback,
    }),
    [
      currentTrack,
      queue,
      upcomingQueue,
      queueIndex,
      isPlaying,
      isShuffle,
      isLoop,
      volume,
      isMuted,
      isQueueOpen,
      isLiked,
      audioProps,
      playTrack,
      playTracks,
      extendQueue,
      togglePlay,
      play,
      pause,
      next,
      previous,
      jumpTo,
      addToQueue,
      removeFromQueue,
      toggleShuffle,
      toggleLoop,
      toggleMute,
      changeVolume,
      toggleQueue,
      toggleLike,
      clearPlayback,
      replaceTrack,
      handoff,
      handoffPlayingElsewhere,
      remoteTrack,
      awaitingGesture,
      radioAvailable,
      radioFeedbackAvailable,
      radioStation,
      radioReason,
      radioReasons,
      startRadio,
      playStation,
      fetchStationBatch,
      stopStation,
      deleteStationById,
      giveStationFeedback,
    ],
  );

  // While another device plays, the progress row is that device's: position
  // interpolated from its last report, the length of its track, and a seek
  // that goes to it as a command.
  const remote = handoff.remote;
  const progressValue = useMemo(() => {
    if (handoffPlayingElsewhere && remote) {
      return {
        currentTime: interpolatedPosition(remote, remoteNowMs),
        duration: Number(remoteTrack?.duration_seconds) || 0,
        seek: remoteSeek,
      };
    }
    return { currentTime, duration, seek };
  }, [handoffPlayingElsewhere, remote, remoteNowMs, remoteTrack, remoteSeek, currentTime, duration, seek]);

  return (
    <PlayerContext.Provider value={value}>
      <PlayerProgressContext.Provider value={progressValue}>
        {children}
      </PlayerProgressContext.Provider>
    </PlayerContext.Provider>
  );
}
