import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Artwork } from "../../components/Artwork";
import { Icon } from "../../components/Icon";
import { PlayerProgress } from "./PlayerProgress";
import { useLibrary } from "../../contexts/LibraryContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { buildAlbumPath, buildArtistPath } from "../../hooks/useNavigation";
import { resolveAlbumArtwork } from "../../utils/artwork";
import { useDismissable } from "../../hooks/useDismissable";
import { HandoffPopover } from "./HandoffPopover";
import { recordArtist } from "../../utils/credits";

export function PlayerBar() {
  const { albumArtworkMap } = useLibrary();
  const {
    currentTrack,
    isPlaying,
    isShuffle,
    isLoop,
    isMuted,
    isQueueOpen,
    isLiked,
    volume,
    audioProps,
    togglePlay,
    next,
    previous,
    toggleShuffle,
    toggleLoop,
    toggleMute,
    changeVolume,
    toggleQueue,
    toggleLike,
    handoff,
    handoffPlayingElsewhere,
    remoteTrack,
    awaitingGesture,
    radioStation,
    radioReason,
  } = usePlayer();

  const [handoffOpen, setHandoffOpen] = useState(false);
  useDismissable(handoffOpen, () => setHandoffOpen(false));

  // When the music is on another device, this bar drives it: every control
  // sends a command, and what the buttons show follows the remote's report.
  // The seek bar does the same through the progress context.
  const remote = handoff?.remote;
  const remotePlaying = Boolean(remote?.playing);
  const displayPlaying = handoffPlayingElsewhere ? remotePlaying : isPlaying;
  const displayShuffle = handoffPlayingElsewhere ? Boolean(remote?.shuffle) : isShuffle;
  const displayLoop = handoffPlayingElsewhere ? Boolean(remote?.loop) : isLoop;
  const onTogglePlay = handoffPlayingElsewhere
    ? () => handoff.sendCommand(remotePlaying ? "pause" : "play")
    : togglePlay;
  const onNext = handoffPlayingElsewhere ? () => handoff.sendCommand("next") : next;
  const onPrevious = handoffPlayingElsewhere ? () => handoff.sendCommand("previous") : previous;
  const onToggleShuffle = handoffPlayingElsewhere
    ? () => handoff.sendCommand("shuffle", { mode: remote?.shuffle ? "off" : "on" })
    : toggleShuffle;
  const onToggleLoop = handoffPlayingElsewhere
    ? () => handoff.sendCommand("repeat", { mode: remote?.loop ? "off" : "queue" })
    : toggleLoop;
  // A drag on the slider fires continuously; the holder needs the last
  // value a few times a second, not every tick.
  const volumeTimer = useRef(null);
  const onVolume = handoffPlayingElsewhere
    ? (value) => {
        clearTimeout(volumeTimer.current);
        volumeTimer.current = setTimeout(() => handoff.sendCommand("volume", { volume: value }), 150);
      }
    : changeVolume;

  // The track shown is the one playing: the holder's while remote.
  const shownTrack = handoffPlayingElsewhere ? remoteTrack || currentTrack : currentTrack;
  const artwork = shownTrack ? resolveAlbumArtwork(shownTrack.album, albumArtworkMap, recordArtist(shownTrack)) : null;
  const playLabel = awaitingGesture ? "Tap to play here" : displayPlaying ? "Pause" : "Play";

  return (
    <footer className="player-bar">
      <div className="player-bar__left">
        {shownTrack ? (
          <>
            <Artwork artwork={artwork} className="player-bar__art" size={52} />

            <div className="player-bar__track-info">
              <div className="player-bar__title-row">
                {displayPlaying && (
                  <span className="eq" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                    <span />
                  </span>
                )}
                <span className="player-bar__title">{shownTrack.title}</span>
                {radioStation?.name && !handoffPlayingElsewhere && (
                  <span className="player-bar__station" title={radioReason || radioStation.name}>
                    <Icon name="radio" size={11} />
                    {radioStation.name}
                  </span>
                )}
              </div>
              <span
                className={`player-bar__meta ${
                  handoffPlayingElsewhere || awaitingGesture ? "player-bar__meta--remote" : ""
                }`}
              >
                {handoffPlayingElsewhere ? (
                  `Playing on ${handoff.activeName}`
                ) : awaitingGesture ? (
                  "Handed to this browser · tap play to continue"
                ) : shownTrack.artist ? (
                  <Link
                    className="player-bar__meta-link"
                    to={buildArtistPath(shownTrack.artist)}
                  >
                    {shownTrack.artist}
                  </Link>
                ) : (
                  "Unknown Artist"
                )}
                {" · "}
                {shownTrack.album ? (
                  <Link
                    className="player-bar__meta-link"
                    to={buildAlbumPath(shownTrack.album)}
                  >
                    {shownTrack.album}
                  </Link>
                ) : (
                  "Unknown Album"
                )}
              </span>
            </div>
          </>
        ) : (
          <span className="player-bar__empty">Nothing playing</span>
        )}
      </div>

      <div className="player-bar__center">
        <div className="player-bar__transport-row">
          <button
            className={`player-bar__icon-button player-bar__like-button ${
              isLiked ? "player-bar__icon-button--active" : ""
            }`}
            type="button"
            aria-label={isLiked ? "Remove from liked songs" : "Add to liked songs"}
            aria-pressed={isLiked}
            onClick={toggleLike}
            disabled={!currentTrack}
          >
            <Icon name="duck" size={20} />
          </button>

          <button
            className={`player-bar__icon-button ${
              displayShuffle ? "player-bar__icon-button--active" : ""
            }`}
            type="button"
            aria-label="Shuffle"
            aria-pressed={displayShuffle}
            onClick={onToggleShuffle}
          >
            <Icon name="shuffle" size={18} />
          </button>

          <button
            className="player-bar__icon-button"
            type="button"
            aria-label="Previous track"
            onClick={onPrevious}
            disabled={!currentTrack && !handoffPlayingElsewhere}
          >
            <Icon name="previous" size={20} />
          </button>

          <button
            className={`player-bar__play-button ${awaitingGesture ? "player-bar__play-button--attention" : ""}`}
            onClick={onTogglePlay}
            type="button"
            aria-label={playLabel}
            title={awaitingGesture ? playLabel : undefined}
            disabled={!currentTrack && !handoffPlayingElsewhere}
          >
            <Icon name={displayPlaying ? "pause" : "play"} size={18} />
          </button>

          <button
            className="player-bar__icon-button"
            type="button"
            aria-label="Next track"
            onClick={onNext}
            disabled={!currentTrack && !handoffPlayingElsewhere}
          >
            <Icon name="next" size={20} />
          </button>

          <button
            className={`player-bar__icon-button ${
              displayLoop ? "player-bar__icon-button--active" : ""
            }`}
            type="button"
            aria-label="Repeat"
            aria-pressed={displayLoop}
            onClick={onToggleLoop}
          >
            <Icon name="repeat" size={18} />
          </button>
        </div>

        <PlayerProgress />
      </div>

      <div className="player-bar__right">
        {handoff?.available ? (
          <div
            className="player-bar__handoff"
            data-dismissable-root={handoffOpen ? "" : undefined}
          >
            <button
              className={`player-bar__icon-button ${
                handoffPlayingElsewhere ? "player-bar__icon-button--remote" : ""
              }`}
              type="button"
              aria-label={
                handoffPlayingElsewhere ? `Playing on ${handoff.activeName}. Change device.` : "Play on another device"
              }
              aria-expanded={handoffOpen}
              onClick={() => setHandoffOpen((open) => !open)}
            >
              <Icon name="handoff" size={18} />
            </button>
            {handoffOpen ? (
              <HandoffPopover
                devices={handoff.devices}
                onChoose={(deviceId) => {
                  setHandoffOpen(false);
                  // "This browser" is a transfer to ourselves: the holder's queue
                  // and position come here. A bare claim kept whatever this tab
                  // had loaded and only silenced the other device.
                  handoff.transferTo(deviceId);
                }}
              />
            ) : null}
          </div>
        ) : null}

        <button
          className={`player-bar__icon-button ${
            isQueueOpen ? "player-bar__icon-button--active" : ""
          }`}
          type="button"
          aria-label="Queue"
          aria-pressed={isQueueOpen}
          onClick={toggleQueue}
        >
          <Icon name="queue" size={18} />
        </button>

        <button
          className="player-bar__icon-button"
          type="button"
          aria-label={isMuted ? "Unmute" : "Mute"}
          onClick={toggleMute}
        >
          <Icon name={isMuted || volume === 0 ? "volumeMute" : "volume"} size={18} />
        </button>

        <input
          className="player-bar__volume-slider"
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={isMuted ? 0 : volume}
          onChange={(event) => onVolume(Number(event.target.value))}
          aria-label="Volume"
        />
      </div>

      {/* The single audio element for the app; the player context owns its ref. */}
      <audio {...audioProps} />
    </footer>
  );
}
