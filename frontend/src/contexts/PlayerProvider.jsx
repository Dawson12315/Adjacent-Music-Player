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
import { getPlaybackState } from "../services/playbackService";
import { getTracksByIds } from "../services/tracksService";
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

  const { currentTrack, queue, queueIndex, isShuffle, isLoop } = state;
  const currentTrackId = currentTrack?.id ?? null;

  // The context playback started from, captured at play time so an event fired after
  // navigating away still records where the track was actually played from.
  const sourceRef = useRef(DEFAULT_SOURCE);

  const handlePlaybackError = useCallback(
    (error) => {
      setIsPlaying(false);

      // Expected when a restored session asks to resume without a user gesture.
      if (error.kind !== "autoplay-blocked") {
        notify(error.message);
      }
    },
    [notify],
  );

  const audio = useAudioElement({
    track: currentTrack,
    isPlaying,
    volume,
    isMuted,
    onPlaybackError: handlePlaybackError,
  });

  const { audioRef, currentTime, duration, seek, requestSeek } = audio;

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

        setIsPlaying(saved.isPlaying);
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

  usePlaybackPersistence({
    enabled: Boolean(currentUser) && hasRestored,
    snapshot,
    getCurrentTime: getPosition,
  });

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

  const playTrack = useCallback(
    (track, sourceTracks = [], source = DEFAULT_SOURCE) => {
      if (currentTrack && currentTrack.id !== track.id && !audioRef.current?.ended) {
        events.skipped(currentTrack);
      }

      sourceRef.current = source;
      dispatch({ type: "PLAY_TRACK", track, sourceTracks });
      setIsPlaying(true);
    },
    [currentTrack, events, audioRef],
  );

  const playTracks = useCallback((tracksToPlay, source = DEFAULT_SOURCE) => {
    if (tracksToPlay.length === 0) return;

    sourceRef.current = source;
    dispatch({ type: "PLAY_TRACKS", tracks: tracksToPlay });
    setIsPlaying(true);
  }, []);

  const togglePlay = useCallback(() => {
    if (!currentTrack) return;
    setIsPlaying((previous) => !previous);
  }, [currentTrack]);

  const play = useCallback(() => {
    if (currentTrack) setIsPlaying(true);
  }, [currentTrack]);

  const pause = useCallback(() => setIsPlaying(false), []);

  const next = useCallback(() => {
    if (currentTrack && !audioRef.current?.ended) {
      events.skipped(currentTrack);
    }

    dispatch({ type: "NEXT" });
  }, [currentTrack, events, audioRef]);

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

    try {
      const liked = wasLiked
        ? await playlistsService.unlikeTrack(currentTrack.id)
        : await playlistsService.likeTrack(currentTrack.id);

      setIsLiked(liked);
      events.likeChanged(currentTrack, !wasLiked);
    } catch (error) {
      notify(error.message || "Could not update your liked songs.");
    }
  }, [currentTrack, isLiked, events, notify]);

  /* ---------- audio element wiring ---------- */

  const handleEnded = useCallback(async () => {
    if (currentTrack) {
      await events.completed(currentTrack);
    }

    if (isLoop) {
      events.resetForTrack(currentTrack);
      seek(0);
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
  }, [currentTrack, events, isLoop, queueIndex, queue.length, seek]);

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
      onPause: () => setIsPlaying(false),
      onEnded: handleEnded,
      onTimeUpdate: audio.handleTimeUpdate,
      onLoadedMetadata: audio.handleLoadedMetadata,
      onError: audio.handleError,
    }),
    [
      audioRef,
      handlePlayEvent,
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
    ],
  );

  const progressValue = useMemo(
    () => ({ currentTime, duration, seek }),
    [currentTime, duration, seek],
  );

  return (
    <PlayerContext.Provider value={value}>
      <PlayerProgressContext.Provider value={progressValue}>
        {children}
      </PlayerProgressContext.Provider>
    </PlayerContext.Provider>
  );
}
