import { useCallback, useEffect, useState } from "react";

import { getPlaylistRecommendations } from "../../services/recommendationsService";
import { getSimilarTracks } from "../../services/tracksService";

const SIMILAR_TRACK_LIMIT = 10;

/**
 * "More like this".
 *
 * Two sources behind one component: per-playlist recommendations when a playlist is
 * open, and per-track similarity otherwise. The playlist variant is slow — it runs the
 * full retrieval pipeline server-side — so requests are aborted when the source changes
 * rather than left to land out of order.
 */
export function SimilarTracksSection({ sourceTrack, playlistId, onPlay, onAdd }) {
  const [tracks, setTracks] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(() => setRefreshKey((previous) => previous + 1), []);

  useEffect(() => {
    if (!playlistId && !sourceTrack) {
      setTracks([]);
      return undefined;
    }

    const controller = new AbortController();

    async function load() {
      setIsLoading(true);

      try {
        const results = playlistId
          ? await getPlaylistRecommendations(playlistId, {
              refresh: refreshKey,
              signal: controller.signal,
            })
          : await getSimilarTracks(sourceTrack.id, { signal: controller.signal });

        if (!controller.signal.aborted) {
          setTracks(results.slice(0, SIMILAR_TRACK_LIMIT));
        }
      } catch (error) {
        if (error.name !== "AbortError") {
          setTracks([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    load();

    return () => controller.abort();
  }, [playlistId, sourceTrack?.id, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  if (tracks.length === 0) {
    return null;
  }

  return (
    <div className="similar-section">
      <div className="similar-section__header">
        <h3>More like this</h3>

        {onAdd && (
          <button
            className="similar-section__refresh-button"
            type="button"
            onClick={refresh}
            disabled={isLoading}
            aria-label="Refresh recommendations"
          >
            ↻
          </button>
        )}
      </div>

      <div className="similar-section__list">
        {tracks.map((track) =>
          onAdd ? (
            <div key={track.id} className="track-row similar-track-row">
              <button
                className="similar-track-row__main"
                onClick={() => onPlay(track)}
                type="button"
              >
                <div className="track-row__content">
                  <div className="track-row__title">{track.title}</div>
                  <div className="track-row__meta">
                    {track.artist || "Unknown Artist"} • {track.album || "Unknown Album"}
                  </div>

                  {track.debug?.reason_summary && (
                    <div className="track-row__reason">{track.debug.reason_summary}</div>
                  )}
                </div>
              </button>

              <button
                className="similar-track-row__add-button"
                type="button"
                onClick={() => onAdd(track)}
                aria-label={`Add ${track.title} to playlist`}
              >
                +
              </button>
            </div>
          ) : (
            <button
              key={track.id}
              className="track-row"
              onClick={() => onPlay(track)}
              type="button"
            >
              <div className="track-row__content">
                <div className="track-row__title">{track.title}</div>
                <div className="track-row__meta">
                  {track.artist || "Unknown Artist"} • {track.album || "Unknown Album"}
                </div>

                {track.debug?.reason_summary && (
                  <div className="track-row__reason">{track.debug.reason_summary}</div>
                )}
              </div>
            </button>
          ),
        )}
      </div>
    </div>
  );
}
