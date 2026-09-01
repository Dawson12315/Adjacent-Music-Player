import { memo } from "react";

import { Artwork } from "../../components/Artwork";
import { Icon } from "../../components/Icon";

/**
 * One row in a track list.
 *
 * The row is a container with two sibling controls rather than a button containing a
 * button — the old markup nested interactive elements, which is invalid and left two
 * elements sharing one accessible name.
 *
 * Memoised because these rows are the bulk of the rendered tree.
 */
export const TrackRow = memo(function TrackRow({
  track,
  index,
  isActive,
  isPlaying,
  artwork,
  playlists,
  isMenuOpen,
  menuDirection,
  onPlay,
  onToggleMenu,
  onEdit,
  onAddToQueue,
  onAddToPlaylist,
  onRemoveFromPlaylist,
  playCount,
}) {
  return (
    <div className={`track-row ${isActive ? "track-row--active" : ""}`}>
      <button
        className="track-row__main"
        onClick={() => onPlay(track)}
        type="button"
        aria-current={isActive ? "true" : undefined}
      >
        <span className="track-row__index">
          {isActive ? (
            <span className={`eq ${isPlaying ? "" : "eq--paused"}`} aria-label="Now playing">
              <span />
              <span />
              <span />
              <span />
            </span>
          ) : (
            index + 1
          )}
        </span>

        <Artwork artwork={artwork} className="track-row__art" size={40} />

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

      <div className="track-row__actions" data-dismissable-root={isMenuOpen ? "" : undefined}>
        {playCount > 0 && (
          <span className="track-row__count" title={`${playCount} plays`}>
            {playCount}
          </span>
        )}

        <button
          className="track-row__menu-button"
          type="button"
          aria-label={`Actions for ${track.title}`}
          aria-expanded={isMenuOpen}
          onClick={(event) => {
            // Flip the menu upwards when there is not enough room below.
            const rect = event.currentTarget.getBoundingClientRect();
            const spaceBelow = window.innerHeight - rect.bottom;

            onToggleMenu(track.id, spaceBelow < 280 ? "up" : "down");
          }}
        >
          <Icon name="more" size={16} />
        </button>

        {isMenuOpen && (
          <div
            className={`menu menu--right ${
              menuDirection === "up" ? "menu--up" : "menu--down"
            }`}
          >
            <button className="menu__item" onClick={() => onEdit(track)} type="button">
              Edit info
            </button>

            <button
              className="menu__item"
              onClick={() => onAddToQueue(track)}
              type="button"
            >
              Add to queue
            </button>

            {playlists.length > 0 && (
              <>
                <div className="menu__divider" />
                <div className="menu__label">Add to playlist</div>

                <div className="menu__scroll">
                  {playlists.map((playlist) => (
                    <button
                      key={playlist.id}
                      className="menu__item"
                      onClick={() => onAddToPlaylist(track.id, playlist.id)}
                      type="button"
                    >
                      {playlist.name}
                    </button>
                  ))}
                </div>
              </>
            )}

            {onRemoveFromPlaylist && (
              <>
                <div className="menu__divider" />
                <button
                  className="menu__item menu__item--danger"
                  onClick={() => onRemoveFromPlaylist(track.id)}
                  type="button"
                >
                  Remove from playlist
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
});
