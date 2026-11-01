import { shuffleItems } from "../../utils/shuffle";

/**
 * The queue state machine.
 *
 * Extracted from six interdependent setState callbacks that nested state updates inside
 * one another. The semantics are unchanged; having them in one pure function is what
 * makes the shuffle/restore and removal index arithmetic testable.
 *
 * Shuffle is *materialised*: turning it on rewrites the upcoming portion of the queue in
 * place and keeps `originalQueue` as the unshuffled record to restore from. That means
 * "previous" is always `queueIndex - 1` in both modes.
 */
export const initialPlayerState = {
  currentTrack: null,
  queue: [],
  originalQueue: [],
  queueIndex: -1,
  isShuffle: false,
  isLoop: false,
};

function withCurrent(state, index) {
  return {
    ...state,
    queueIndex: index,
    currentTrack: state.queue[index] ?? state.currentTrack,
  };
}

export function playerReducer(state, action) {
  switch (action.type) {
    /**
     * Play a track from a list. Everything up to and including the clicked track keeps
     * its order; when shuffle is on, only what comes after it is shuffled.
     */
    case "PLAY_TRACK": {
      const { track, sourceTracks } = action;
      const clickedIndex = sourceTracks.findIndex((item) => item.id === track.id);

      if (clickedIndex === -1) {
        // Not part of the visible list (a recommendation, say): play it on its own.
        return {
          ...state,
          currentTrack: track,
          queue: [track],
          originalQueue: [track],
          queueIndex: 0,
        };
      }

      const originalQueue = [...sourceTracks];
      const upcoming = originalQueue.slice(clickedIndex + 1);

      const queue = state.isShuffle
        ? [...originalQueue.slice(0, clickedIndex + 1), ...shuffleItems(upcoming)]
        : originalQueue;

      return {
        ...state,
        currentTrack: track,
        queue,
        originalQueue,
        queueIndex: clickedIndex,
      };
    }

    /**
     * The list the queue was built from grew (a paged genre or library feed
     * loading its next pages while playing). When `tracks` is a strict
     * extension of that list, same ids in the same positions and then more,
     * the new tail joins the queue. In order it is appended; shuffled, the
     * unplayed remainder and the tail are shuffled as one, so a shuffle of
     * a genre draws from the whole genre and not from its first page.
     */
    case "EXTEND_QUEUE": {
      const { tracks } = action;
      const known = state.originalQueue;

      if (!known.length || !Array.isArray(tracks) || tracks.length <= known.length) {
        return state;
      }

      const samePrefix = known.every((track, index) => track.id === tracks[index]?.id);

      if (!samePrefix) {
        return state;
      }

      if (!state.isShuffle) {
        return { ...state, queue: tracks, originalQueue: tracks };
      }

      const played = state.queue.slice(0, state.queueIndex + 1);
      const upcoming = state.queue.slice(state.queueIndex + 1);
      const tail = tracks.slice(known.length);

      return {
        ...state,
        queue: [...played, ...shuffleItems([...upcoming, ...tail])],
        originalQueue: tracks,
      };
    }

    /**
     * More of the same list, behind what is queued: a station's next batch.
     * Appended in the order given whatever the shuffle setting, because a
     * station's order is the station's to decide; tracks already in the
     * queue are left out.
     */
    case "APPEND_TRACKS": {
      const have = new Set(state.queue.map((track) => track.id));
      const fresh = (Array.isArray(action.tracks) ? action.tracks : []).filter((track) => {
        if (track?.id == null || have.has(track.id)) return false;
        have.add(track.id);
        return true;
      });
      if (!fresh.length) return state;
      return {
        ...state,
        queue: [...state.queue, ...fresh],
        originalQueue: [...state.originalQueue, ...fresh],
      };
    }

    /**
     * What is up next is replaced; what has played and what is playing stay.
     * "Fresh batch" on a station.
     */
    case "REPLACE_UPCOMING": {
      const tracks = Array.isArray(action.tracks) ? action.tracks : [];
      const played = state.queue.slice(0, state.queueIndex + 1);
      const keep = new Set(played.map((track) => track.id));
      const fresh = tracks.filter((track) => track?.id != null && !keep.has(track.id));
      if (!fresh.length) return state;
      return {
        ...state,
        queue: [...played, ...fresh],
        originalQueue: [...played, ...fresh],
      };
    }

    /**
     * Upcoming tracks the listener said no to leave the queue: by id, or by
     * artist. What has played and what is playing stay where they are.
     */
    case "REMOVE_UPCOMING": {
      const ids = new Set((action.trackIds || []).map(String));
      const artists = new Set((action.artists || []).filter(Boolean).map((name) => String(name).toLowerCase()));
      const doomed = (track, position) =>
        position > state.queueIndex &&
        (ids.has(String(track?.id)) || artists.has(String(track?.artist || "").toLowerCase()));
      const queue = state.queue.filter((track, position) => !doomed(track, position));
      if (queue.length === state.queue.length) return state;
      const gone = new Set(state.queue.filter(doomed).map((track) => track.id));
      return {
        ...state,
        queue,
        originalQueue: state.originalQueue.filter((track) => !gone.has(track.id)),
      };
    }

    /** Play a whole list from the top, used by "play playlist". */
    case "PLAY_TRACKS": {
      const { tracks } = action;

      if (tracks.length === 0) {
        return state;
      }

      return {
        ...state,
        currentTrack: tracks[0],
        queue: tracks,
        originalQueue: tracks,
        queueIndex: 0,
      };
    }

    case "NEXT": {
      if (state.queue.length === 0 || state.queueIndex === -1) {
        return state;
      }

      if (state.queueIndex >= state.queue.length - 1) {
        return state;
      }

      return withCurrent(state, state.queueIndex + 1);
    }

    case "PREVIOUS": {
      if (state.queue.length === 0 || state.queueIndex <= 0) {
        return state;
      }

      return withCurrent(state, state.queueIndex - 1);
    }

    case "JUMP_TO": {
      const { index } = action;

      if (index < 0 || index >= state.queue.length) {
        return state;
      }

      return withCurrent(state, index);
    }

    case "ADD_TO_QUEUE": {
      return {
        ...state,
        queue: [...state.queue, action.track],
        originalQueue: [...state.originalQueue, action.track],
      };
    }

    case "REMOVE_AT": {
      const { index } = action;
      const trackToRemove = state.queue[index];

      if (!trackToRemove) {
        return state;
      }

      const queue = state.queue.filter((_, position) => position !== index);

      const originalIndex = state.originalQueue.findIndex(
        (track, position) => position >= state.queueIndex && track.id === trackToRemove.id,
      );

      const originalQueue =
        originalIndex === -1
          ? state.originalQueue
          : state.originalQueue.filter((_, position) => position !== originalIndex);

      // Removing something already played shifts the current position back by one.
      if (index < state.queueIndex) {
        return {
          ...state,
          queue,
          originalQueue,
          queueIndex: state.queueIndex - 1,
        };
      }

      // Removing the playing track: fall through to whatever now occupies its slot.
      if (index === state.queueIndex) {
        if (queue.length === 0) {
          return {
            ...state,
            queue,
            originalQueue,
            queueIndex: -1,
            currentTrack: null,
          };
        }

        const nextIndex = Math.min(state.queueIndex, queue.length - 1);

        return {
          ...state,
          queue,
          originalQueue,
          queueIndex: nextIndex,
          currentTrack: queue[nextIndex] ?? null,
        };
      }

      return { ...state, queue, originalQueue };
    }

    case "TOGGLE_SHUFFLE": {
      const isShuffle = !state.isShuffle;

      if (state.queue.length === 0 || state.queueIndex < 0) {
        return { ...state, isShuffle };
      }

      if (isShuffle) {
        return {
          ...state,
          isShuffle,
          queue: [
            ...state.queue.slice(0, state.queueIndex + 1),
            ...shuffleItems(state.queue.slice(state.queueIndex + 1)),
          ],
        };
      }

      // Turning shuffle off restores the original order and re-finds the current track.
      const currentTrack = state.queue[state.queueIndex];
      const restoredIndex = currentTrack
        ? state.originalQueue.findIndex((track) => track.id === currentTrack.id)
        : -1;

      return {
        ...state,
        isShuffle,
        queue: state.originalQueue,
        queueIndex: restoredIndex === -1 ? state.queueIndex : restoredIndex,
      };
    }

    case "TOGGLE_LOOP":
      return { ...state, isLoop: !state.isLoop };

    /** Rehydrate from the server-side playback session on load. */
    case "RESTORE": {
      const { queue, queueIndex, currentTrack, isShuffle, isLoop } = action;

      return {
        ...state,
        queue,
        originalQueue: queue,
        queueIndex,
        currentTrack,
        isShuffle,
        isLoop,
      };
    }

    /** Keep an edited track's new metadata everywhere it is referenced. */
    case "REPLACE_TRACK": {
      const { track } = action;
      const swap = (item) => (item.id === track.id ? track : item);

      return {
        ...state,
        queue: state.queue.map(swap),
        originalQueue: state.originalQueue.map(swap),
        currentTrack:
          state.currentTrack?.id === track.id ? track : state.currentTrack,
      };
    }

    case "CLEAR":
      return { ...initialPlayerState, isShuffle: state.isShuffle, isLoop: state.isLoop };

    default:
      return state;
  }
}
