import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Artwork } from "../../components/Artwork";
import { Icon } from "../../components/Icon";
import { useLibrary } from "../../contexts/LibraryContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { useNavigation } from "../../hooks/useNavigation";
import { getStation } from "../../services/radioService";
import { resolveAlbumArtwork, resolveStationArtwork } from "../../utils/artwork";
import { creditLine, recordArtist } from "../../utils/credits";
import { stationKindLabel } from "../player/radio";

/**
 * The station's own page: what is playing on it, what is lined up, and why
 * each track is there. Opened by Start radio, by the station chip in the
 * player bar, and by a station card on Home.
 *
 * The seed's picture as a banner with the station chip on it, the name, a
 * line with the kind and the place in the batch, then Pause, Skip and
 * Fresh batch, then the batch as a list with the playing row lit and the
 * station's reason under every track. A click on a row jumps to it; the
 * list grows as the station refills.
 *
 * A station that is not the one playing (an old link, a card on Home) is
 * shown with its name and a Play button; its list exists only once it
 * plays, because the batch is the player's queue.
 */
export function StationView() {
  const navigate = useNavigate();
  const { selectedStationId } = useNavigation();
  const { albumArtworkMap } = useLibrary();
  const {
    radioStation,
    radioReasons = {},
    queue,
    queueIndex,
    currentTrack,
    isPlaying,
    togglePlay,
    next,
    jumpTo,
    fetchStationBatch,
    playStation,
  } = usePlayer();

  const live = radioStation && Number(radioStation.id) === Number(selectedStationId);
  const [station, setStation] = useState(live ? radioStation : null);
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);

  // Not the playing station: look it up for its name and picture.
  useEffect(() => {
    if (live) {
      setStation(radioStation);
      setMissing(false);
      return undefined;
    }
    if (selectedStationId == null) return undefined;
    const controller = new AbortController();
    getStation(selectedStationId, { signal: controller.signal })
      .then((found) => {
        if (!controller.signal.aborted) setStation(found);
      })
      .catch(() => {
        if (!controller.signal.aborted) setMissing(true);
      });
    return () => controller.abort();
  }, [live, radioStation, selectedStationId]);

  const upcoming = live && queueIndex >= 0 ? queue.slice(queueIndex) : [];
  const position = live && queueIndex >= 0 ? queueIndex + 1 : 0;
  const total = live ? queue.length : 0;

  const freshBatch = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await fetchStationBatch?.();
    } finally {
      setBusy(false);
    }
  };

  const playThisStation = async () => {
    if (!station || busy) return;
    setBusy(true);
    try {
      await playStation?.(station);
    } finally {
      setBusy(false);
    }
  };

  if (missing) {
    return (
      <div className="state">
        <div className="state__icon">
          <Icon name="radio" size={20} />
        </div>
        <p className="state__title">That station is gone</p>
        <p className="state__text">
          It was deleted, or it belongs to another account. <Link to="/">Back to Home</Link>.
        </p>
      </div>
    );
  }

  const artwork = station ? resolveStationArtwork(station) : null;

  return (
    <section className="station-page">
      <button className="station-page__back" type="button" onClick={() => navigate(-1)}>
        <Icon name="chevronLeft" size={16} />
        Back
      </button>

      <div className="station-page__banner">
        {artwork && <Artwork artwork={artwork} className="station-page__banner-art" size={720} eager />}
        <span className="station-page__chip">
          <Icon name="radio" size={12} />
          {station?.name || "Radio"}
        </span>
      </div>

      <h1 className="page-header__title">{station?.name || "Radio"}</h1>
      <p className="station-page__line">
        {stationKindLabel(station)}
        {total > 0 ? ` · ${position} of ${total}` : ""}
        {live ? " · more arrives as it plays" : ""}
      </p>

      <div className="station-page__controls">
        {live ? (
          <>
            <button className="btn btn--accent" type="button" onClick={togglePlay}>
              <Icon name={isPlaying ? "pause" : "play"} size={14} />
              {isPlaying ? "Pause" : "Play"}
            </button>
            <button className="btn btn--ghost" type="button" onClick={next}>
              <Icon name="next" size={14} />
              Skip
            </button>
            <button className="btn btn--ghost" type="button" onClick={freshBatch} disabled={busy} aria-busy={busy || undefined}>
              <Icon name="refresh" size={14} className={busy ? "icon--spin" : undefined} />
              Fresh batch
            </button>
          </>
        ) : (
          <button className="btn btn--accent" type="button" onClick={playThisStation} disabled={!station || busy}>
            <Icon name="play" size={14} />
            Play this station
          </button>
        )}
      </div>

      <h2 className="section-head__title station-page__section">Up next on the station</h2>

      {live ? (
        <div className="track-list">
          {upcoming.map((track, offset) => {
            const index = queueIndex + offset;
            const active = currentTrack?.id === track.id && offset === 0;
            const reason = radioReasons[String(track.id)];
            return (
              <div key={`${track.id}:${index}`} className={`track-row ${active ? "track-row--active" : ""}`}>
                <button
                  className="track-row__main"
                  type="button"
                  onClick={() => jumpTo(index)}
                  aria-current={active ? "true" : undefined}
                  aria-label={`Play ${track.title}`}
                >
                  <span className="track-row__index">
                    {active ? (
                      <span className={`eq ${isPlaying ? "" : "eq--paused"}`} aria-label="Now playing">
                        <span />
                        <span />
                        <span />
                        <span />
                      </span>
                    ) : (
                      offset + 1
                    )}
                  </span>
                  <Artwork
                    artwork={resolveAlbumArtwork(track.album, albumArtworkMap, recordArtist(track))}
                    className="track-row__art"
                    size={40}
                  />
                  <span className="track-row__content">
                    <span className="track-row__title">{track.title}</span>
                    <span className="track-row__meta">
                      {creditLine(track)} · {track.album || "Unknown Album"}
                    </span>
                    {reason && <span className="track-row__reason">{reason}</span>}
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="rail__empty">
          {station ? "Play the station to see what it lines up." : "Loading the station…"}
        </p>
      )}
    </section>
  );
}
