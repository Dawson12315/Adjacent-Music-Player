import { useState } from "react";
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
  } = usePlayer();

  const [handoffOpen, setHandoffOpen] = useState(false);
  useDismissable(handoffOpen, () => setHandoffOpen(false));

  // When the music is on another device, this bar drives it: the controls send
  // commands, and what the play button shows follows the remote's report.
  const remotePlaying = Boolean(handoff?.remote?.playing);
  const displayPlaying = handoffPlayingElsewhere ? remotePlaying : isPlaying;
  const onTogglePlay = handoffPlayingElsewhere
    ? () => handoff.sendCommand(remotePlaying ? "pause" : "play")
    : togglePlay;
  const onNext = handoffPlayingElsewhere ? () => handoff.sendCommand("next") : next;
  const onPrevious = handoffPlayingElsewhere ? () => handoff.sendCommand("previous") : previous;

  const artwork = currentTrack ? resolveAlbumArtwork(currentTrack.album, albumArtworkMap, currentTrack.artist) : null;

  return (
    <footer className="player-bar">
      <div className="player-bar__left">
        {currentTrack ? (
          <>
            <Artwork artwork={artwork} className="player-bar__art" size={52} />

            <div className="player-bar__track-info">
              <div className="player-bar__title-row">
                {isPlaying && (
                  <span className="eq" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                    <span />
                  </span>
                )}
                <span className="player-bar__title">{currentTrack.title}</span>
              </div>
              <span className={`player-bar__meta ${handoffPlayingElsewhere ? "player-bar__meta--remote" : ""}`}>
                {handoffPlayingElsewhere ? (
                  `Playing on ${handoff.activeName}`
                ) : currentTrack.artist ? (
                  <Link
                    className="player-bar__meta-link"
                    to={buildArtistPath(currentTrack.artist)}
                  >
                    {currentTrack.artist}
                  </Link>
                ) : (
                  "Unknown Artist"
                )}
                {" · "}
                {currentTrack.album ? (
                  <Link
                    className="player-bar__meta-link"
                    to={buildAlbumPath(currentTrack.album)}
                  >
                    {currentTrack.album}
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
              isShuffle ? "player-bar__icon-button--active" : ""
            }`}
            type="button"
            aria-label="Shuffle"
            aria-pressed={isShuffle}
            onClick={toggleShuffle}
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
            className="player-bar__play-button"
            onClick={onTogglePlay}
            type="button"
            aria-label={displayPlaying ? "Pause" : "Play"}
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
              isLoop ? "player-bar__icon-button--active" : ""
            }`}
            type="button"
            aria-label="Repeat"
            aria-pressed={isLoop}
            onClick={toggleLoop}
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
                  if (handoff.me && deviceId === handoff.me.deviceId) handoff.claim();
                  else handoff.transferTo(deviceId);
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
          onChange={(event) => changeVolume(Number(event.target.value))}
          aria-label="Volume"
        />
      </div>

      {/* The single audio element for the app; the player context owns its ref. */}
      <audio {...audioProps} />
    </footer>
  );
}
