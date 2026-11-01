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
import { feedbackState, isWideReason, stationKindLabel, stationLine } from "../player/radio";

/**
 * The station's own page: what is playing on it, what is lined up, and why
 * each track is there. Opened by Start radio, by the station chip in the
 * player bar, and by a station card on Home.
 *
 * The seed's picture as a banner with the station chip on it, the name, a
 * line with the kind and the place in the batch, then Pause, Skip, Fresh
 * batch (what is up next is replaced), Stop and Remove; then the batch as a
 * list with the playing row lit and the station's reason under every
 * track. Each row takes a word back: more like this, not this one, less of
 * this artist. A click on a row jumps to it; the list grows as the station
 * refills, and what has played can be unfolded above it.
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
    radioReasons,
    radioFeedbackAvailable = false,
    queue,
    queueIndex,
    currentTrack,
    isPlaying,
    isLoop,
    togglePlay,
    next,
    jumpTo,
    fetchStationBatch,
    playStation,
    stopStation,
    deleteStationById,
    giveStationFeedback,
  } = usePlayer();

  const live = radioStation && Number(radioStation.id) === Number(selectedStationId);
  const [station, setStation] = useState(live ? radioStation : null);
  // "gone" is a 404 or 410; anything else is "failed", with a retry.
  const [problem, setProblem] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [showPlayed, setShowPlayed] = useState(false);

  // Not the playing station: look it up for its name and picture.
  useEffect(() => {
    setProblem(null);
    if (live) {
      setStation(radioStation);
      return undefined;
    }
    if (selectedStationId == null || !Number.isFinite(selectedStationId)) {
      setProblem("gone");
      return undefined;
    }
    const controller = new AbortController();
    getStation(selectedStationId, { signal: controller.signal })
      .then((found) => {
        if (!controller.signal.aborted) setStation(found);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setProblem(error?.status === 404 || error?.status === 410 ? "gone" : "failed");
      });
    return () => controller.abort();
  }, [live, radioStation, selectedStationId, attempt]);

  const upcoming = live && queueIndex >= 0 ? queue.slice(queueIndex) : [];
  const played = live && queueIndex > 0 ? queue.slice(0, queueIndex) : [];
  const position = live && queueIndex >= 0 ? queueIndex + 1 : 0;
  const total = live ? queue.length : 0;
  const feedback = (live ? radioStation : station)?.feedback;

  const run = async (action) => {
    if (busy) return;
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  };

  const freshBatch = () => run(() => fetchStationBatch?.());
  const playThisStation = () => run(() => station && playStation?.(station));
  const stopThisStation = () => {
    stopStation?.();
    navigate(-1);
  };
  const removeThisStation = () =>
    run(async () => {
      const removed = await deleteStationById?.(station?.id ?? selectedStationId);
      if (removed) navigate("/radio", { replace: true });
    });

  if (problem === "gone") {
    return (
      <div className="state">
        <div className="state__icon">
          <Icon name="radio" size={20} />
        </div>
        <p className="state__title">That station is gone</p>
        <p className="state__text">
          It was removed, or its seed left the library. <Link to="/radio">All stations</Link> · <Link to="/">Home</Link>.
        </p>
      </div>
    );
  }

  if (problem === "failed") {
    return (
      <div className="state">
        <div className="state__icon">
          <Icon name="radio" size={20} />
        </div>
        <p className="state__title">Couldn't load this station</p>
        <p className="state__text">Your server did not answer.</p>
        <button className="btn btn--ghost btn--sm" type="button" onClick={() => setAttempt((value) => value + 1)}>
          <Icon name="refresh" size={14} />
          Try again
        </button>
      </div>
    );
  }

  const artwork = station ? resolveStationArtwork(station) : null;

  const renderRow = (track, index, { active = false, number = null } = {}) => {
    const reason = radioReasons?.get?.(String(track.id)) || null;
    const said = feedbackState(feedback, track);
    return (
      <div key={`${track.id}:${index}`} className={`track-row station-row ${active ? "track-row--active" : ""}`}>
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
              number
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
            {reason && (
              <span className={`track-row__reason ${isWideReason(reason) ? "track-row__reason--wide" : ""}`}>{reason}</span>
            )}
          </span>
        </button>
        {radioFeedbackAvailable && giveStationFeedback && (
          <span className="station-row__say" role="group" aria-label={`What to say about ${track.title}`}>
            <button
              className={`station-say ${said.more ? "station-say--on" : ""}`}
              type="button"
              title={said.more ? "Taken as a seed. Click to take it back." : "More like this"}
              aria-label={`More like ${track.title}`}
              aria-pressed={said.more}
              onClick={() => giveStationFeedback(track, "more")}
            >
              <Icon name="thumbUp" size={14} />
            </button>
            <button
              className={`station-say ${said.less ? "station-say--on" : ""}`}
              type="button"
              title={said.less ? "Kept off this station. Click to take it back." : "Not this one"}
              aria-label={`Not ${track.title} on this station`}
              aria-pressed={said.less}
              onClick={() => giveStationFeedback(track, "less")}
            >
              <Icon name="thumbDown" size={14} />
            </button>
            {track.artist && (
              <button
                className={`station-say ${said.lessArtist ? "station-say--on" : ""}`}
                type="button"
                title={said.lessArtist ? `${track.artist} is kept out. Click to take it back.` : `Less of ${track.artist}`}
                aria-label={`Less of ${track.artist} on this station`}
                aria-pressed={said.lessArtist}
                onClick={() => giveStationFeedback(track, "less_artist")}
              >
                <Icon name="less" size={14} />
              </button>
            )}
          </span>
        )}
      </div>
    );
  };

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
        {stationLine({ kind: stationKindLabel(station), position, total, live: Boolean(live), isLoop })}
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
            <button
              className="btn btn--ghost"
              type="button"
              onClick={freshBatch}
              disabled={busy}
              aria-busy={busy || undefined}
              title="Replace what is up next with a fresh batch"
            >
              <Icon name="refresh" size={14} className={busy ? "icon--spin" : undefined} />
              Fresh batch
            </button>
            <button className="btn btn--ghost" type="button" onClick={stopThisStation} title="Stop the station; what is queued plays on">
              <Icon name="stop" size={14} />
              Stop station
            </button>
          </>
        ) : (
          <button className="btn btn--accent" type="button" onClick={playThisStation} disabled={!station || busy}>
            <Icon name="play" size={14} />
            Play this station
          </button>
        )}
        {station && deleteStationById && (
          confirmRemove ? (
            <span className="station-page__confirm">
              <button className="btn btn--danger btn--sm" type="button" onClick={removeThisStation} disabled={busy}>
                Remove {station.name}
              </button>
              <button className="btn btn--ghost btn--sm" type="button" onClick={() => setConfirmRemove(false)}>
                Keep it
              </button>
            </span>
          ) : (
            <button className="btn btn--ghost" type="button" onClick={() => setConfirmRemove(true)} title="Remove this station and what it remembers">
              <Icon name="close" size={14} />
              Remove
            </button>
          )
        )}
      </div>

      {live && played.length > 0 && (
        <button className="station-page__played" type="button" onClick={() => setShowPlayed((value) => !value)} aria-expanded={showPlayed}>
          <Icon name={showPlayed ? "chevronLeft" : "chevronRight"} size={12} />
          {played.length === 1 ? "1 track played on this station" : `${played.length} tracks played on this station`}
        </button>
      )}
      {live && showPlayed && played.length > 0 && (
        <div className="track-list station-page__history">
          {played.map((track, index) => renderRow(track, index, { number: index + 1 }))}
        </div>
      )}

      <h2 className="section-head__title station-page__section">Up next on the station</h2>

      {live ? (
        <div className="track-list">
          {upcoming.map((track, offset) =>
            renderRow(track, queueIndex + offset, {
              active: currentTrack?.id === track.id && offset === 0,
              number: offset + 1,
            }),
          )}
        </div>
      ) : (
        <p className="rail__empty">
          {station ? "Play the station to see what it lines up." : "Loading the station…"}
        </p>
      )}
    </section>
  );
}
