import { PlayerProgress } from "./PlayerProgress";
import { useLibrary } from "../../contexts/LibraryContext";
import { usePlayer } from "../../contexts/PlayerContext";
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

  const artwork = currentTrack?.album
    ? resolveAlbumArtwork(currentTrack.album, albumArtworkMap)
    : null;

  return (
    <footer className="player-bar">
      <div className="player-bar__left">
        {currentTrack ? (
          <>
            {artwork?.type === "image" ? (
              <img
                className="player-bar__art"
                src={artwork.src}
                alt={currentTrack.album || currentTrack.title}
              />
            ) : (
              <div className="player-bar__art player-bar__art--placeholder">♪</div>
            )}

            <div className="player-bar__track-info">
              <div className="player-bar__title">{currentTrack.title}</div>
              <div className="player-bar__meta">
                {currentTrack.artist || "Unknown Artist"} •{" "}
                {currentTrack.album || "Unknown Album"}
              </div>
            </div>
          </>
        ) : (
          <div className="player-bar__meta">Nothing playing</div>
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
            {isLiked ? "♥" : "♡"}
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
            ⇄
          </button>

          <button
            className="player-bar__icon-button"
            type="button"
            aria-label="Previous track"
            onClick={previous}
          >
            ⏮
          </button>

          <button
            className="player-bar__play-button"
            onClick={togglePlay}
            type="button"
            aria-label={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? "❚❚" : "▶"}
          </button>

          <button
            className="player-bar__icon-button"
            type="button"
            aria-label="Next track"
            onClick={next}
          >
            ⏭
          </button>

          <button
            className={`player-bar__icon-button ${
              isLoop ? "player-bar__icon-button--active" : ""
            }`}
            type="button"
            aria-label="Loop"
            aria-pressed={isLoop}
            onClick={toggleLoop}
          >
            ↺
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
          ☰
        </button>

        <button
          className="player-bar__icon-button"
          type="button"
          aria-label={isMuted ? "Unmute" : "Mute"}
          onClick={toggleMute}
        >
          {isMuted || volume === 0 ? "🔇" : "🔊"}
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
