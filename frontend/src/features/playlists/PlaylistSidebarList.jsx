import { useState } from "react";
import { NavLink } from "react-router-dom";

import { Artwork } from "../../components/Artwork";
import { ArtworkUploadModal } from "../../components/ArtworkUploadModal";
import { Icon } from "../../components/Icon";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { useArtworkUpload } from "../../hooks/useArtworkUpload";
import { useDismissable } from "../../hooks/useDismissable";
import { buildPlaylistPath } from "../../hooks/useNavigation";
import { getPlaylistTracks } from "../../services/playlistsService";
import { resolvePlaylistArtwork } from "../../utils/artwork";

export function PlaylistSidebarList({ onNavigate }) {
  const {
    playlists,
    createPlaylist,
    renamePlaylist,
    deletePlaylist,
    updatePlaylistArtwork,
  } = useLibrary();
  const { playTracks } = usePlayer();
  const { notify } = useNotifications();

  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [openMenuId, setOpenMenuId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState("");
  const [artworkPlaylist, setArtworkPlaylist] = useState(null);
  const [isSavingArtwork, setIsSavingArtwork] = useState(false);

  const upload = useArtworkUpload();
  useDismissable(openMenuId !== null, () => setOpenMenuId(null));

  async function handleCreate() {
    const trimmed = newName.trim();
    if (!trimmed) return;

    try {
      await createPlaylist(trimmed);
      setNewName("");
      setIsCreating(false);
      notify(`Created "${trimmed}".`);
    } catch (error) {
      notify(error.message || "Could not create that playlist.");
    }
  }

  async function handleRename(playlistId) {
    const trimmed = editingName.trim();

    if (!trimmed) {
      setEditingId(null);
      return;
    }

    try {
      await renamePlaylist(playlistId, trimmed);
    } catch (error) {
      notify(error.message || "Could not rename that playlist.");
    } finally {
      setEditingId(null);
      setEditingName("");
    }
  }

  async function handleDelete(playlist) {
    try {
      await deletePlaylist(playlist.id);
      notify(`Deleted "${playlist.name}".`);
    } catch (error) {
      notify(error.message || "Could not delete that playlist.");
    } finally {
      setOpenMenuId(null);
    }
  }

  /** Clicking the artwork plays the playlist; clicking the name opens it. */
  async function handlePlay(playlist) {
    try {
      const tracks = await getPlaylistTracks(playlist.id);

      if (tracks.length === 0) {
        notify("That playlist is empty.");
        return;
      }

      playTracks(tracks, { source_type: "playlist", source_id: playlist.id });
    } catch (error) {
      notify(error.message || "Could not play that playlist.");
    }
  }

  function openArtworkEditor(playlist) {
    setArtworkPlaylist(playlist);
    upload.setExistingArtwork(playlist.artwork_path);
    setOpenMenuId(null);
  }

  async function saveArtwork() {
    if (!artworkPlaylist || !upload.file) return;

    setIsSavingArtwork(true);

    try {
      await updatePlaylistArtwork(artworkPlaylist.id, upload.file);
      setArtworkPlaylist(null);
      upload.reset();
    } catch (error) {
      notify(error.message || "Could not upload the artwork.");
    } finally {
      setIsSavingArtwork(false);
    }
  }

  return (
    <div className="sidebar__section">
      <div className="sidebar__section-header">
        <span className="sidebar__section-title">Playlists</span>

        <button
          className="sidebar__section-action"
          type="button"
          aria-label="Create playlist"
          onClick={() => setIsCreating((open) => !open)}
        >
          <Icon name="plus" size={16} />
        </button>
      </div>

      {isCreating && (
        <div className="playlist-create">
          <input
            className="input"
            style={{ height: 32, fontSize: "var(--text-xs)" }}
            type="text"
            placeholder="Playlist name"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") handleCreate();
              if (event.key === "Escape") {
                setIsCreating(false);
                setNewName("");
              }
            }}
            autoFocus
          />
        </div>
      )}

      {playlists.length === 0 ? (
        <p className="sidebar__stat">No playlists yet</p>
      ) : (
        playlists.map((playlist) => (
          <div className="playlist-item" key={playlist.id}>
            {editingId === playlist.id ? (
              <input
                className="input"
                style={{ height: 32, fontSize: "var(--text-xs)" }}
                type="text"
                value={editingName}
                autoFocus
                onChange={(event) => setEditingName(event.target.value)}
                onBlur={() => setEditingId(null)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") handleRename(playlist.id);
                  if (event.key === "Escape") setEditingId(null);
                }}
              />
            ) : (
              <NavLink
                to={buildPlaylistPath(playlist.id)}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `playlist-item__main ${isActive ? "playlist-item--active" : ""}`
                }
              >
                <span
                  className="playlist-item__art"
                  role="button"
                  tabIndex={0}
                  aria-label={`Play ${playlist.name}`}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    handlePlay(playlist);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      event.stopPropagation();
                      handlePlay(playlist);
                    }
                  }}
                >
                  <Artwork artwork={resolvePlaylistArtwork(playlist)} size={36} />
                  <span className="playlist-item__art-overlay">
                    <Icon name="play" size={14} />
                  </span>
                </span>

                <span className="playlist-item__name">{playlist.name}</span>
              </NavLink>
            )}

            {!playlist.is_system && (
              <div data-dismissable-root={openMenuId === playlist.id ? "" : undefined}>
                <button
                  className="playlist-item__menu-button"
                  type="button"
                  aria-label={`Actions for ${playlist.name}`}
                  aria-expanded={openMenuId === playlist.id}
                  onClick={() =>
                    setOpenMenuId((current) =>
                      current === playlist.id ? null : playlist.id,
                    )
                  }
                >
                  <Icon name="more" size={14} />
                </button>

                {openMenuId === playlist.id && (
                  <div className="menu menu--right menu--down">
                    <button
                      className="menu__item"
                      type="button"
                      onClick={() => openArtworkEditor(playlist)}
                    >
                      Change artwork
                    </button>
                    <button
                      className="menu__item"
                      type="button"
                      onClick={() => {
                        setEditingId(playlist.id);
                        setEditingName(playlist.name);
                        setOpenMenuId(null);
                      }}
                    >
                      Rename
                    </button>
                    <div className="menu__divider" />
                    <button
                      className="menu__item menu__item--danger"
                      type="button"
                      onClick={() => handleDelete(playlist)}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))
      )}

      {artworkPlaylist && (
        <ArtworkUploadModal
          title="Change playlist artwork"
          previewLabel={artworkPlaylist.name}
          previewUrl={upload.previewUrl}
          fileName={upload.file?.name}
          onSelectFile={upload.selectFile}
          onSave={saveArtwork}
          onClose={() => {
            setArtworkPlaylist(null);
            upload.reset();
          }}
          isSaving={isSavingArtwork}
        />
      )}
    </div>
  );
}
