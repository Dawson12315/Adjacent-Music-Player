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
