import { Artwork } from "../../components/Artwork";
import { Icon } from "../../components/Icon";
import { formatListeningTime, formatPercent, useInsightsData } from "./useInsightsData";
import { useLibrary } from "../../contexts/LibraryContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { resolveAlbumArtwork } from "../../utils/artwork";

/**
 * Listening analytics.
 *
 * The previous version showed four tiles containing the *length of a list* — always "10"
 * — and four ranked lists with no numbers on them, because the API ordered by the
 * counters and then threw them away. Everything here is a real magnitude.
 */
export function InsightsView() {
  const data = useInsightsData();
  const { albumArtworkMap } = useLibrary();
  const { playTrack } = usePlayer();

  const { summary } = data;
  const hasHistory = summary && summary.total_plays > 0;

  if (data.isLoading && !summary) {
    return (
      <div className="insights">
        <div className="insights__summary">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="stat-tile">
              <div className="skeleton skeleton--text" style={{ width: "50%" }} />
              <div
                className="skeleton skeleton--title"
                style={{ height: 28, marginTop: 12 }}
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!hasHistory) {
    return (
      <div className="state">
        <div className="state__icon">
          <Icon name="insights" size={20} />
        </div>
        <p className="state__title">No listening data yet</p>
        <p className="state__text">
          Play a few tracks and this fills in — what you play most, what you skip, when
          you listen, and where you start from.
        </p>
      </div>
    );
  }

  const listening = formatListeningTime(summary.estimated_listening_seconds);
  const maxPlays = Math.max(...data.playsOverTime.map((d) => d.plays), 1);
  const maxHour = Math.max(...data.byHour.map((h) => h.plays), 1);

  return (
    <div className="insights">
      <div className="insights__summary">
        <StatTile icon="play" label="Total plays" value={summary.total_plays.toLocaleString()} />

        <StatTile
          icon="clock"
          label="Listening time"
          value={listening.value}
          unit={listening.unit}
          note="Estimated from playback"
        />

        <StatTile
          icon="music"
          label="Completion rate"
          value={formatPercent(summary.completion_rate)}
          note={`${summary.total_completions.toLocaleString()} finished`}
        />

        <StatTile
          icon="skip"
          label="Skip rate"
          value={formatPercent(summary.skip_rate)}
          note={`${summary.total_skips.toLocaleString()} skipped`}
        />

        <StatTile
          icon="sparkle"
          label="Tracks played"
          value={summary.distinct_tracks_played.toLocaleString()}
          note={`${summary.distinct_artists_played.toLocaleString()} artists`}
        />

        <StatTile
          icon="repeat"
          label="Current streak"
          value={summary.current_streak_days}
          unit={summary.current_streak_days === 1 ? "day" : "days"}
          note={`Longest ${summary.longest_streak_days}`}
        />
      </div>

      {data.playsOverTime.length > 0 && (
        <section className="insights__panel insights__panel--full">
          <div className="section-head">
            <h2 className="section-head__title">Plays over time</h2>
            <span className="section-head__link">Last 30 days</span>
          </div>

          <div className="chart">
            {data.playsOverTime.map((day) => (
              <div
                key={day.date}
                className={`chart__bar ${day.plays === 0 ? "chart__bar--empty" : ""}`}
                style={{ height: `${Math.max((day.plays / maxPlays) * 100, 2)}%` }}
                title={`${day.date}: ${day.plays} plays`}
              />
            ))}
          </div>

          <div className="chart__axis">
            <span>{data.playsOverTime[0]?.date}</span>
            <span>{data.playsOverTime.at(-1)?.date}</span>
          </div>
        </section>
      )}

      <div className="insights__grid">
        <BarPanel
          title="Top artists"
          rows={data.topArtists.map((a) => ({ label: a.name, value: a.play_count }))}
        />

        <BarPanel
          title="Top albums"
          rows={data.topAlbums.map((a) => ({
            label: a.name,
            sub: a.artist,
            value: a.play_count,
          }))}
        />

        <BarPanel
          title="Top genres"
          rows={data.topGenres.map((g) => ({ label: g.name, value: g.play_count }))}
        />

        <BarPanel
          title="Where you listen from"
          rows={data.bySource.map((s) => ({ label: labelForSource(s.source), value: s.plays }))}
        />
      </div>

      {data.byHour.length > 0 && (
        <section className="insights__panel insights__panel--full">
          <div className="section-head">
            <h2 className="section-head__title">When you listen</h2>
          </div>

          <div className="hour-grid">
            {data.byHour.map((hour) => (
              <div
                key={hour.hour}
                className="hour-cell"
                title={`${String(hour.hour).padStart(2, "0")}:00 — ${hour.plays} plays`}
                style={{
                  background:
                    hour.plays === 0
                      ? "var(--wash)"
                      : `color-mix(in srgb, var(--blue) ${Math.round(
                          20 + (hour.plays / maxHour) * 80,
                        )}%, transparent)`,
                }}
              />
            ))}
          </div>

          <div className="hour-grid__axis">
            <span>00:00</span>
            <span>12:00</span>
            <span>23:00</span>
          </div>
        </section>
      )}

      <div className="insights__grid">
        <TrackPanel
          title="Most played"
          icon="play"
          tracks={data.topPlayed}
          countKey="play_count"
          unit="plays"
          albumArtworkMap={albumArtworkMap}
          onPlay={playTrack}
        />

        <TrackPanel
          title="Most loved"
          icon="heartFilled"
          tracks={data.mostLiked}
          countKey="like_count"
          unit="likes"
          albumArtworkMap={albumArtworkMap}
          onPlay={playTrack}
        />

        <TrackPanel
          title="Most skipped"
          icon="skip"
          tracks={data.mostSkipped}
          countKey="skip_count"
          unit="skips"
          albumArtworkMap={albumArtworkMap}
          onPlay={playTrack}
        />
      </div>

      <div className="settings-card__actions settings-card__actions--footer">
        <button className="btn btn--sm" type="button" onClick={data.refresh}>
          <Icon name="refresh" size={14} />
          Refresh
        </button>
      </div>
    </div>
  );
}

function StatTile({ icon, label, value, unit, note }) {
  return (
    <div className="stat-tile">
      <div className="stat-tile__label">
        <Icon name={icon} size={14} />
        {label}
      </div>
      <div className="stat-tile__value">
        {value}
        {unit && <span className="stat-tile__unit">{unit}</span>}
      </div>
      {note && <div className="stat-tile__note">{note}</div>}
    </div>
  );
}

function BarPanel({ title, rows }) {
  if (rows.length === 0) {
    return null;
  }

  const max = Math.max(...rows.map((row) => row.value), 1);

  return (
    <section className="insights__panel">
      <div className="section-head">
        <h2 className="section-head__title">{title}</h2>
      </div>

      <div className="bar-list">
        {rows.map((row) => (
          <div className="bar-row" key={`${row.label}-${row.sub || ""}`}>
            <span className="bar-row__label">
              {row.label}
              {row.sub && <span className="bar-row__value"> · {row.sub}</span>}
            </span>
            <span className="bar-row__value">{row.value.toLocaleString()}</span>
            <span className="bar-row__track">
              <span
                className="bar-row__fill"
                style={{ width: `${Math.max((row.value / max) * 100, 3)}%` }}
              />
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function TrackPanel({ title, icon, tracks, countKey, unit, albumArtworkMap, onPlay }) {
  return (
    <section className="insights__panel">
      <div className="section-head">
        <h2 className="section-head__title">
          <Icon name={icon} size={16} /> {title}
        </h2>
      </div>

      {tracks.length === 0 ? (
        <p className="state__text">Not enough listening yet.</p>
      ) : (
        <div className="track-list">
          {tracks.map((track, index) => (
            <div className="track-row" key={track.id}>
              <button
                className="track-row__main"
                type="button"
                onClick={() =>
                  onPlay(track, tracks, { source_type: "library", source_id: null })
                }
              >
                <span className="track-row__index">{index + 1}</span>
                <Artwork
                  artwork={resolveAlbumArtwork(track.album, albumArtworkMap)}
                  className="track-row__art"
                  size={40}
                />
                <span className="track-row__content">
                  <span className="track-row__title">{track.title}</span>
                  <span className="track-row__meta">{track.artist || "Unknown Artist"}</span>
                </span>
              </button>

              <span className="track-row__count">
                {(track[countKey] || 0).toLocaleString()} {unit}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function labelForSource(source) {
  return (
    {
      library: "Library browsing",
      playlist: "Playlists",
      artist: "Artist pages",
      album: "Album pages",
      recommendation: "Recommendations",
      queue: "Queue",
      unknown: "Unknown",
    }[source] || source
  );
}
