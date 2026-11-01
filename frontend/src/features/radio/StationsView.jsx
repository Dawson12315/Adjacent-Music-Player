import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Artwork } from "../../components/Artwork";
import { Icon } from "../../components/Icon";
import { usePlayer } from "../../contexts/PlayerContext";
import { buildStationPath } from "../../hooks/useNavigation";
import { getStations } from "../../services/radioService";
import { resolveStationArtwork } from "../../utils/artwork";
import { STATIONS_CHANGED_EVENT, stationKindLabel } from "../player/radio";

/**
 * Every station the listener has, the one played last first: the Home rail
 * shows twelve, this shows them all, each with Play and Remove. The one
 * playing is marked.
 */
export function StationsView() {
  const navigate = useNavigate();
  const { radioStation, radioAvailable, playStation, deleteStationById } = usePlayer();
  const [stations, setStations] = useState(null);
  const [failed, setFailed] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const load = () =>
      getStations({ limit: 50, signal: controller.signal })
        .then((rows) => {
          if (!controller.signal.aborted) {
            setStations(Array.isArray(rows) ? rows : []);
            setFailed(false);
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) setFailed(true);
        });
    load();
    window.addEventListener(STATIONS_CHANGED_EVENT, load);
    return () => {
      controller.abort();
      window.removeEventListener(STATIONS_CHANGED_EVENT, load);
    };
  }, [attempt]);

  const play = async (station) => {
    if (busyId) return;
    setBusyId(station.id);
    try {
      const played = await playStation?.(station);
      if (played) navigate(buildStationPath(station.id));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (station) => {
    if (busyId) return;
    setBusyId(station.id);
    try {
      const removed = await deleteStationById?.(station.id);
      if (removed) setStations((previous) => (previous || []).filter((item) => item.id !== station.id));
    } finally {
      setBusyId(null);
      setRemoving(null);
    }
  };

  return (
    <section className="station-page stations-page">
      <h1 className="page-header__title">
        <Icon name="radio" size={22} /> Radio
      </h1>
      <p className="station-page__line">
        {radioAvailable
          ? "Your stations, the one played last first. Start one from any track's menu, or from an album or artist page."
          : "Radio needs a newer Adjacent server."}
      </p>

      {failed && (
        <div className="state">
          <p className="state__title">Couldn't load your stations</p>
          <button className="btn btn--ghost btn--sm" type="button" onClick={() => setAttempt((value) => value + 1)}>
            <Icon name="refresh" size={14} />
            Try again
          </button>
        </div>
      )}

      {!failed && stations && stations.length === 0 && (
        <p className="rail__empty">No stations yet.</p>
      )}

      {!failed && stations && stations.length > 0 && (
        <div className="track-list">
          {stations.map((station) => {
            const playing = radioStation?.id === station.id;
            const busy = busyId === station.id;
            return (
              <div key={station.id} className={`track-row station-row ${playing ? "track-row--active" : ""}`}>
                <button
                  className="track-row__main"
                  type="button"
                  onClick={() => (playing ? navigate(buildStationPath(station.id)) : play(station))}
                  aria-label={playing ? `Open ${station.name}` : `Play ${station.name}`}
                  aria-busy={busy || undefined}
                  disabled={busy}
                >
                  <span className="track-row__index">
                    <Icon name={playing ? "radio" : "play"} size={14} />
                  </span>
                  <Artwork artwork={resolveStationArtwork(station)} className="track-row__art" size={40} />
                  <span className="track-row__content">
                    <span className="track-row__title">{station.name}</span>
                    <span className="track-row__meta">
                      {stationKindLabel(station)}
                      {playing ? " · playing now" : ""}
                    </span>
                  </span>
                </button>
                <span className="station-row__say">
                  {removing === station.id ? (
                    <>
                      <button className="btn btn--danger btn--sm" type="button" onClick={() => remove(station)} disabled={busy}>
                        Remove
                      </button>
                      <button className="btn btn--ghost btn--sm" type="button" onClick={() => setRemoving(null)}>
                        Keep
                      </button>
                    </>
                  ) : (
                    <button
                      className="station-say"
                      type="button"
                      title={`Remove ${station.name}`}
                      aria-label={`Remove ${station.name}`}
                      onClick={() => setRemoving(station.id)}
                      disabled={busy}
                    >
                      <Icon name="close" size={14} />
                    </button>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
