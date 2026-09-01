import { Link } from "react-router-dom";

import { Artwork } from "../../components/Artwork";
import { Icon } from "../../components/Icon";
import { PlayerProgress } from "./PlayerProgress";
import { useLibrary } from "../../contexts/LibraryContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { buildAlbumPath, buildArtistPath } from "../../hooks/useNavigation";
import { resolveAlbumArtwork } from "../../utils/artwork";

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
  } = usePlayer();

  const artwork = currentTrack ? resolveAlbumArtwork(currentTrack.album, albumArtworkMap) : null;

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
              <span className="player-bar__meta">
                {currentTrack.artist ? (
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
            <Icon name={isLiked ? "heartFilled" : "heart"} size={18} />
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
            onClick={previous}
            disabled={!currentTrack}
          >
            <Icon name="previous" size={20} />
          </button>

          <button
            className="player-bar__play-button"
            onClick={togglePlay}
            type="button"
            aria-label={isPlaying ? "Pause" : "Play"}
            disabled={!currentTrack}
          >
            <Icon name={isPlaying ? "pause" : "play"} size={18} />
          </button>

          <button
            className="player-bar__icon-button"
            type="button"
            aria-label="Next track"
            onClick={next}
            disabled={!currentTrack}
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
