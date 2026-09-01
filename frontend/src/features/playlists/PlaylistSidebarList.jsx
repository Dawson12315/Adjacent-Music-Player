import { useState } from "react";

import { ArtworkUploadModal } from "../../components/ArtworkUploadModal";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer } from "../../contexts/PlayerContext";
import { useArtworkUpload } from "../../hooks/useArtworkUpload";
import { useNavigation } from "../../hooks/useNavigation";
import { getPlaylistTracks } from "../../services/playlistsService";
import { resolvePlaylistArtwork } from "../../utils/artwork";

export function PlaylistSidebarList() {
  const {
    playlists,
    createPlaylist,
    renamePlaylist,
    deletePlaylist,
    updatePlaylistArtwork,
  } = useLibrary();
  const { playTracks } = usePlayer();
  const { activeView, selectedPlaylistId, goToPlaylist, clearFilters } = useNavigation();
  const { notify } = useNotifications();

  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [openMenuId, setOpenMenuId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState("");
  const [artworkPlaylist, setArtworkPlaylist] = useState(null);
  const [isSavingArtwork, setIsSavingArtwork] = useState(false);

  const upload = useArtworkUpload();

  async function handleCreate() {
    const trimmed = newName.trim();
    if (!trimmed) return;

    try {
      await createPlaylist(trimmed);
      setNewName("");
      setIsCreating(false);
    } catch (error) {
      notify(error.message || "Could not create that playlist.");
    }
  }

  async function handleRename(playlistId) {
    const trimmed = editingName.trim();

    if (!trimmed) {
      setEditingId(null);
      setEditingName("");
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

  async function handleDelete(playlistId) {
    try {
      await deletePlaylist(playlistId);

      if (selectedPlaylistId === playlistId) {
        clearFilters();
      }
    } catch (error) {
      notify(error.message || "Could not delete that playlist.");
    } finally {
      setOpenMenuId(null);
    }
  }

  /** Clicking the artwork plays the playlist; clicking the name just opens it. */
  async function handlePlay(playlist) {
    try {
      const tracks = await getPlaylistTracks(playlist.id);

      if (tracks.length === 0) {
        notify("That playlist is empty.");
        return;
      }

      goToPlaylist(playlist.id);
      playTracks(tracks, { source_type: "playlist", source_id: playlist.id });
    } catch (error) {
      notify(error.message || "Could not play that playlist.");
    } finally {
      setOpenMenuId(null);
    }
  }

  function openArtworkEditor(playlist) {
    setArtworkPlaylist(playlist);
    upload.setExistingArtwork(playlist.artwork_path);
    setOpenMenuId(null);
  }

  function closeArtworkEditor() {
    setArtworkPlaylist(null);
    upload.reset();
  }

  async function saveArtwork() {
    if (!artworkPlaylist || !upload.file) return;

    setIsSavingArtwork(true);

    try {
      await updatePlaylistArtwork(artworkPlaylist.id, upload.file);
      closeArtworkEditor();
    } catch (error) {
      notify(error.message || "Could not upload the playlist artwork.");
    } finally {
      setIsSavingArtwork(false);
    }
  }

  return (
    <div className="sidebar__section sidebar__section--playlists">
      <div className="sidebar__section-header">
        <div className="sidebar__section-title">Playlists</div>

        <button
          className="sidebar__section-action"
          type="button"
          aria-label="Create playlist"
          onClick={() => setIsCreating((previous) => !previous)}
        >
          +
        </button>
      </div>

      {isCreating && (
        <div className="playlist-create">
          <input
            className="playlist-create__input"
            type="text"
            placeholder="New Playlist"
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

          <button className="playlist-create__button" type="button" onClick={handleCreate}>
            Create
          </button>
        </div>
      )}

      {playlists.length === 0 ? (
        <div className="sidebar__stat">No playlists yet</div>
      ) : (
        playlists.map((playlist) => {
          const artwork = resolvePlaylistArtwork(playlist);
          const isActive = activeView === "playlist" && selectedPlaylistId === playlist.id;

          return (
            <div key={playlist.id} className="playlist-sidebar-item">
              {editingId === playlist.id ? (
                <input
                  className="playlist-sidebar-item__input"
                  type="text"
                  value={editingName}
                  autoFocus
                  onChange={(event) => setEditingName(event.target.value)}
                  onBlur={() => {
                    setEditingId(null);
                    setEditingName("");
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") handleRename(playlist.id);
                    if (event.key === "Escape") {
                      setEditingId(null);
                      setEditingName("");
                    }
                  }}
                />
              ) : (
                <div
                  className={`playlist-sidebar-item__main ${
                    isActive ? "sidebar__link--active" : ""
                  }`}
                >
                  <div
                    className="playlist-art-wrapper"
                    onClick={() => handlePlay(playlist)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        handlePlay(playlist);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    aria-label={`Play ${playlist.name}`}
                  >
                    {artwork.type === "image" ? (
                      <img className="playlist-art" src={artwork.src} alt="" />
                    ) : (
                      <div className={`playlist-art ${artwork.gradientClass}`}>
                        <span className="playlist-art__initials">{artwork.initials}</span>
                      </div>
                    )}

                    <div className="playlist-art__overlay" />
                  </div>

                  <button
                    className="playlist-sidebar-item__name-button"
                    type="button"
                    onClick={() => goToPlaylist(playlist.id)}
                  >
                    {playlist.name}
                  </button>
                </div>
              )}

              {!playlist.is_system && (
                <div className="playlist-sidebar-item__actions">
                  <button
                    className="playlist-sidebar-item__menu-button"
                    type="button"
                    aria-label={`Actions for ${playlist.name}`}
                    aria-expanded={openMenuId === playlist.id}
                    onClick={(event) => {
                      event.stopPropagation();
                      setOpenMenuId((previous) =>
                        previous === playlist.id ? null : playlist.id,
                      );
                    }}
                  >
                    ⋯
                  </button>

                  {openMenuId === playlist.id && (
                    <div
                      className="playlist-sidebar-item__menu"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <button
                        className="playlist-sidebar-item__menu-item"
                        type="button"
                        onClick={() => openArtworkEditor(playlist)}
                      >
                        Change Artwork
                      </button>

                      <button
                        className="playlist-sidebar-item__menu-item"
                        type="button"
                        onClick={() => {
                          setEditingId(playlist.id);
                          setEditingName(playlist.name);
                          setOpenMenuId(null);
                        }}
                      >
                        Rename Playlist
                      </button>

                      <button
                        className="playlist-sidebar-item__menu-item"
                        type="button"
                        onClick={() => handleDelete(playlist.id)}
                      >
                        Delete Playlist
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}

      {artworkPlaylist && (
        <ArtworkUploadModal
          title="Change Artwork"
          previewLabel={artworkPlaylist.name}
          previewUrl={upload.previewUrl}
          fileName={upload.file?.name}
          onSelectFile={upload.selectFile}
          onSave={saveArtwork}
          onClose={closeArtworkEditor}
          isSaving={isSavingArtwork}
        />
      )}
    </div>
  );
}
