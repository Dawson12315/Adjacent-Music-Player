import { memo } from "react";

/**
 * One row in a track list, with its actions menu.
 *
 * The outer element is still a <button> containing the menu button, matching the
 * original markup and the stylesheet that targets it. That nesting is invalid HTML and
 * is on the list for the accessibility pass; changing the element here would change what
 * the existing CSS matches, so it is left alone deliberately.
 *
 * Memoised because these rows are the bulk of the rendered tree.
 */
export const TrackRow = memo(function TrackRow({
  track,
  index,
  isActive,
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
}) {
  return (
    <button
      className={`track-row ${isActive ? "track-row--active" : ""}`}
      onClick={() => onPlay(track)}
      type="button"
    >
      <div className="track-row__index-group">
        <div className="track-row__index">{index + 1}</div>

        {artwork?.type === "image" ? (
          <img className="track-row__album-art" src={artwork.src} alt={track.album || ""} />
        ) : (
          <div className="track-row__album-art track-row__album-art--placeholder">♪</div>
        )}
      </div>

      <div className="track-row__content">
        <div className="track-row__title">{track.title}</div>
        <div className="track-row__meta">
          {track.artist || "Unknown Artist"} • {track.album || "Unknown Album"}
        </div>
      </div>

      <div className="track-row__actions">
        <button
          className="track-row__menu-button"
          type="button"
          aria-label={`Actions for ${track.title}`}
          aria-expanded={isMenuOpen}
          onClick={(event) => {
            event.stopPropagation();

            // Flip the menu upwards when there is not enough room below.
            const rect = event.currentTarget.getBoundingClientRect();
            const spaceBelow = window.innerHeight - rect.bottom;

            onToggleMenu(track.id, spaceBelow < 260 ? "up" : "down");
          }}
        >
          ⋯
        </button>

        {isMenuOpen && (
          <div
            className={`track-row__menu ${
              menuDirection === "up" ? "track-row__menu--up" : ""
            }`}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="track-row__menu-item"
              onClick={() => onEdit(track)}
              type="button"
            >
              Edit Info
            </button>

            <button
              className="track-row__menu-item"
              onClick={() => onAddToQueue(track)}
              type="button"
            >
              Add to Queue
            </button>

            {playlists.length > 0 && (
              <>
                <div className="track-row__menu-divider" />
                <div className="track-row__menu-label">Add to Playlist</div>

                {playlists.map((playlist) => (
                  <button
                    key={playlist.id}
                    className="track-row__menu-item"
                    onClick={() => onAddToPlaylist(track.id, playlist.id)}
                    type="button"
                  >
                    {playlist.name}
                  </button>
                ))}
              </>
            )}

            {onRemoveFromPlaylist && (
              <>
                <div className="track-row__menu-divider" />
                <button
                  className="track-row__menu-item"
                  onClick={() => onRemoveFromPlaylist(track.id)}
                  type="button"
                >
                  Remove from Playlist
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </button>
  );
});
