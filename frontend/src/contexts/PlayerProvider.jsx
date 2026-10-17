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
import { getPlaybackState } from "../services/playbackService";
import { getTracksByIds } from "../services/tracksService";
import { interpolatedPosition } from "../services/handoffProtocol";
import * as playlistsService from "../services/playlistsService";
import { initialPlayerState, playerReducer } from "../features/player/playerReducer";

const DEFAULT_SOURCE = { source_type: "library", source_id: null };

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

  // The context playback started from, captured at play time so an event fired after
  // navigating away still records where the track was actually played from.
  const sourceRef = useRef(DEFAULT_SOURCE);

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

  const { audioRef, currentTime, duration, seek, requestSeek, hasPendingSeek } = audio;

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

        const restoredTrack =
          restoredQueue[saved.queueIndex] ??
          (saved.currentTrackId
            ? (await getTracksByIds([saved.currentTrackId]))[0] ?? null
            : null);

        if (cancelled) return;

        dispatch({
          type: "RESTORE",
          queue: restoredQueue,
          queueIndex: saved.queueIndex,
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
  }, [currentUser, libraryLoading, hasRestored, requestSeek]);

  /* ---------- persistence ---------- */

  const queueTrackIds = useMemo(() => queue.map((track) => track.id), [queue]);

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

      await claimBeforePlay({ trackId: track.id, position: 0, playing: true });
      sourceRef.current = source;
      dispatch({ type: "PLAY_TRACK", track, sourceTracks });
      setIsPlaying(true);
    },
    [currentTrack, events, audioRef, claimBeforePlay],
  );

  const playTracks = useCallback(
    async (tracksToPlay, source = DEFAULT_SOURCE) => {
      if (tracksToPlay.length === 0) return;

      await claimBeforePlay({ trackId: tracksToPlay[0]?.id ?? null, position: 0, playing: true });
      sourceRef.current = source;
      dispatch({ type: "PLAY_TRACKS", tracks: tracksToPlay });
      setIsPlaying(true);
    },
    [claimBeforePlay],
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

  const next = useCallback(() => {
    // The reducer ignores Next at the end of the list; say so, or a Next that
    // does nothing reads as a player that has stopped working.
    if (queue.length > 0 && queueIndex >= queue.length - 1) {
      notify("That was the last track in the list.");
      return;
    }

    if (currentTrack && !audioRef.current?.ended) {
      events.skipped(currentTrack);
    }

    dispatch({ type: "NEXT" });
  }, [currentTrack, events, audioRef, queue.length, queueIndex, notify]);

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
  const toggleLoop = useCallback(() => dispatch({ type: "TOGGLE_LOOP" }), []);
  const replaceTrack = useCallback((track) => dispatch({ type: "REPLACE_TRACK", track }), []);

  const clearPlayback = useCallback(() => {
    dispatch({ type: "CLEAR" });
    setIsPlaying(false);
  }, []);

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

    // Stop at the end of the queue rather than wrapping around.
    if (queueIndex === -1 || queueIndex >= queue.length - 1) {
      setIsPlaying(false);
      return;
    }

    dispatch({ type: "NEXT" });
    setIsPlaying(true);
  }, [currentTrack, events, isLoop, queueIndex, queue.length, seek, audioRef]);

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

    if (currentTrack) {
      events.playStarted(currentTrack);
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
      playing: isPlaying,
      shuffle: isShuffle,
      loop: isLoop,
      source: getSource(),
    }),
    [currentTrackId, queueTrackIds, queueIndex, getPosition, isPlaying, isShuffle, isLoop, getSource],
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
        dispatch({
          type: "RESTORE",
          queue: tracks,
          queueIndex: idx,
          currentTrack: startTrack,
          isShuffle: Boolean(serverState.is_shuffle),
          isLoop: Boolean(serverState.is_loop),
        });
        const position = Number(serverState.current_time_seconds) || 0;
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
    [dispatch, requestSeek],
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
        case "seek":
          if (Number.isFinite(Number(args?.position))) seek(Number(args.position));
          break;
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
    [currentTrack, next, previous, seek, isShuffle, toggleShuffle, isLoop, toggleLoop, changeVolume],
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
      if (Number.isFinite(seconds)) handoffSendCommand("seek", { position: Math.max(0, Math.floor(seconds)) });
    },
    [handoffSendCommand],
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
    deviceId: handoff.me?.deviceId ?? null,
  });

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
