import { useCallback, useEffect, useState } from "react";

import { useLibrary } from "../../contexts/LibraryContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { getStatsOverview } from "../../services/statsService";
import { getAlbumKey, resolveAlbumArtwork } from "../../utils/artwork";

const EMPTY_OVERVIEW = {
  top_played: [],
  most_liked: [],
  most_skipped: [],
  recently_played: [],
};

const CARDS = [
  { key: "top_played", title: "Top Played", subtitle: "Your strongest repeat listens.", icon: "▶" },
  { key: "most_liked", title: "Most Loved", subtitle: "Tracks you keep close.", icon: "♥" },
  {
    key: "most_skipped",
    title: "Most Skipped",
    subtitle: "Useful negative feedback for recommendations.",
    icon: "↷",
  },
  {
    key: "recently_played",
    title: "Recently Played",
    subtitle: "Your latest listening trail.",
    icon: "⏱",
  },
];

const SUMMARY = [
  { key: "top_played", label: "Top Played", icon: "▶", modifier: "played" },
  { key: "most_liked", label: "Most Loved", icon: "♥", modifier: "loved" },
  { key: "most_skipped", label: "Most Skipped", icon: "↷", modifier: "skipped" },
  { key: "recently_played", label: "Recently Played", icon: "⏱", modifier: "recent" },
];

/**
 * Stats load when this view is opened and on demand from the refresh control.
 *
 * Previously every listening event — every play, skip, like and completion — triggered a
 * full stats refetch regardless of whether this screen was even open.
 */
export function InsightsView() {
  const { albumArtworkMap, ensureAlbumArtwork } = useLibrary();
  const { playTrack } = usePlayer();

  const [overview, setOverview] = useState(EMPTY_OVERVIEW);
  const [isLoading, setIsLoading] = useState(false);

  const load = useCallback(async (signal) => {
    setIsLoading(true);

    try {
      const data = await getStatsOverview({ signal });

      if (!signal?.aborted) {
        setOverview(data);
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        console.error("Failed to load insights", error);
      }
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  // Stats responses never carry artwork, so it comes from the shared album cache.
  const albumKeys = CARDS.flatMap(({ key }) =>
    (overview[key] || []).map((track) => getAlbumKey(track.album)).filter(Boolean),
  );

  const signature = albumKeys.join("|");

  useEffect(() => {
    if (albumKeys.length > 0) {
      ensureAlbumArtwork(albumKeys);
    }
  }, [signature, ensureAlbumArtwork]); // eslint-disable-line react-hooks/exhaustive-deps

  function renderTrack(track, prefix, index, sourceTracks) {
    const artwork = track.album ? resolveAlbumArtwork(track.album, albumArtworkMap) : null;

    return (
      <button
        key={`${prefix}-${track.id}`}
        className="insight-track-row"
        type="button"
        onClick={() => playTrack(track, sourceTracks, {
          source_type: "library",
          source_id: null,
        })}
      >
        <div className="insight-track-row__rank">{index + 1}</div>

        {artwork?.type === "image" ? (
          <img className="insight-track-row__art" src={artwork.src} alt="" />
        ) : (
          <div className="insight-track-row__art insight-track-row__art--placeholder">
            ♪
          </div>
        )}

        <div className="insight-track-row__content">
          <div className="insight-track-row__title">{track.title}</div>
          <div className="insight-track-row__meta">{track.artist || "Unknown Artist"}</div>
        </div>
      </button>
    );
  }

  return (
    <div className="behavior-insights-page">
      <div className="behavior-insights-hero behavior-insights-hero--polished">
        <div>
          <div className="behavior-insights-eyebrow">Listening analytics</div>
          <h2>Behavior Insights</h2>
          <p>See what you play most, skip most, love most, and listened to recently.</p>
        </div>

        <button
          className="settings-button settings-button--secondary behavior-insights-refresh"
          type="button"
          onClick={() => load()}
          disabled={isLoading}
        >
          {isLoading ? "Refreshing..." : "Refresh insights"}
        </button>
      </div>

      <div className="behavior-insights-summary">
        {SUMMARY.map(({ key, label, icon, modifier }) => (
          <div
            key={key}
            className={`behavior-insights-stat behavior-insights-stat--${modifier}`}
          >
            <div className="behavior-insights-stat__icon">{icon}</div>
            <div>
              <div className="behavior-insights-stat__label">{label}</div>
              <div className="behavior-insights-stat__value">
                {(overview[key] || []).length}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="behavior-insights-grid">
        {CARDS.map(({ key, title, subtitle, icon }) => {
          const cardTracks = overview[key] || [];

          return (
            <div key={key} className="insights-card">
              <div className="insights-card__header">
                <div className="insights-card__icon">{icon}</div>
                <div>
                  <h3>{title}</h3>
                  <p>{subtitle}</p>
                </div>
              </div>

              <div className="insights-card__list">
                {cardTracks.length === 0 ? (
                  <div className="insights-empty">
                    <div className="insights-empty__icon">♪</div>
                    <div>
                      <div className="insights-empty__title">No listening data yet</div>
                      <div className="insights-empty__text">
                        Play, love, or skip more tracks to fill this in.
                      </div>
                    </div>
                  </div>
                ) : (
                  cardTracks
                    .slice(0, 5)
                    .map((track, index) => renderTrack(track, key, index, cardTracks))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
