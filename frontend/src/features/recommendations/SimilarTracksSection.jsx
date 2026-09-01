import { useCallback, useEffect, useState } from "react";

import { Artwork } from "../../components/Artwork";
import { Icon } from "../../components/Icon";
import { useLibrary } from "../../contexts/LibraryContext";
import { getPlaylistRecommendations } from "../../services/recommendationsService";
import { getSimilarTracks } from "../../services/tracksService";
import { resolveAlbumArtwork } from "../../utils/artwork";

const LIMIT = 10;

/**
 * "More like this".
 *
 * Two sources behind one component: per-playlist recommendations when a playlist is open,
 * and per-track similarity otherwise. Both now run the real retrieval pipeline — the
 * track endpoint used to be `WHERE genre = ? ORDER BY random()`, which never touched the
 * Last.fm similarity tables, the co-occurrence data, or listening behaviour.
 */
export function SimilarTracksSection({ sourceTrack, playlistId, onPlay, onAdd }) {
  const { albumArtworkMap } = useLibrary();

  const [tracks, setTracks] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

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
          setTracks(results.slice(0, LIMIT));
        }
      } catch (error) {
        if (error.name !== "AbortError") setTracks([]);
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }

    load();

    return () => controller.abort();
  }, [playlistId, sourceTrack?.id, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  if (tracks.length === 0) {
    return null;
  }

  return (
    <section className="similar-section">
      <div className="similar-section__header">
        <h2 className="section-head__title">
          <Icon name="sparkle" size={16} /> More like this
        </h2>

        <button
          className="btn btn--icon btn--ghost btn--sm"
          type="button"
          onClick={refresh}
          disabled={isLoading}
          aria-label="Refresh recommendations"
        >
          <Icon name="refresh" size={14} />
        </button>
      </div>

      <div className="similar-section__list">
        {tracks.map((track) => (
          <div className="track-row" key={track.id}>
            <button className="track-row__main" type="button" onClick={() => onPlay(track)}>
              <span className="track-row__index">
                <Icon name="play" size={12} />
              </span>
              <Artwork
                artwork={resolveAlbumArtwork(track.album, albumArtworkMap)}
                className="track-row__art"
                size={40}
              />
              <span className="track-row__content">
                <span className="track-row__title">{track.title}</span>
                <span className="track-row__meta">
                  {track.artist || "Unknown Artist"} · {track.album || "Unknown Album"}
                </span>
                {track.debug?.reason_summary && (
                  <span className="track-row__reason">{track.debug.reason_summary}</span>
                )}
              </span>
            </button>

            {onAdd && (
              <div className="track-row__actions">
                <button
                  className="btn btn--icon btn--ghost btn--sm"
                  type="button"
                  onClick={() => onAdd(track)}
                  aria-label={`Add ${track.title} to this playlist`}
                >
                  <Icon name="plus" size={16} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
