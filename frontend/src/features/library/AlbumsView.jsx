import { useEffect, useState } from "react";

import { ArtworkUploadModal } from "../../components/ArtworkUploadModal";
import { SearchBar } from "../../components/SearchBar";
import { ViewToggle } from "../../components/ViewToggle";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { useArtworkUpload } from "../../hooks/useArtworkUpload";
import { useNavigation } from "../../hooks/useNavigation";
import { uploadAlbumArtwork } from "../../services/albumsService";
import { getAlbumKey, resolveAlbumArtwork } from "../../utils/artwork";
import { useLibraryFilters } from "./useLibraryFilters";

const ARTWORK_PREFETCH_LIMIT = 80;

const VIEW_OPTIONS = [
  { value: "grid", label: "Grid" },
  { value: "list", label: "List" },
];

export function AlbumsView() {
  const { albumArtworkMap, ensureAlbumArtwork, setAlbumArtwork } = useLibrary();
  const { searchQuery, setSearchQuery, goToAlbum } = useNavigation();
  const { notify } = useNotifications();
  const { visibleAlbums } = useLibraryFilters();

  const [viewMode, setViewMode] = useState("grid");
  const [artworkAlbum, setArtworkAlbum] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  const upload = useArtworkUpload();

  const prefetchAlbums = visibleAlbums.slice(0, ARTWORK_PREFETCH_LIMIT);
  const signature = prefetchAlbums.join("|");

  useEffect(() => {
    if (prefetchAlbums.length > 0) {
      ensureAlbumArtwork(prefetchAlbums.map(getAlbumKey));
    }
  }, [signature, ensureAlbumArtwork]); // eslint-disable-line react-hooks/exhaustive-deps

  function openArtworkEditor(album) {
    setArtworkAlbum(album);
    upload.setExistingArtwork(albumArtworkMap[getAlbumKey(album)]);
  }

  function closeArtworkEditor() {
    setArtworkAlbum(null);
    upload.reset();
  }

  async function saveArtwork() {
    if (!artworkAlbum || !upload.file) {
      return;
    }

    setIsSaving(true);

    try {
      const result = await uploadAlbumArtwork(artworkAlbum, upload.file);
      setAlbumArtwork(getAlbumKey(artworkAlbum), result.artwork_path || "");
      closeArtworkEditor();
    } catch (error) {
      notify(error.message || "Could not upload the album artwork.");
    } finally {
      setIsSaving(false);
    }
  }

  function renderArtwork(album, sizeClass) {
    const artwork = resolveAlbumArtwork(album, albumArtworkMap);
    const base = viewMode === "grid" ? "album-card__art" : "album-list-row__art";

    if (artwork.type === "image") {
      return <img className={`${base} ${sizeClass}`} src={artwork.src} alt="" />;
    }

    return (
      <div className={`${base} ${base}--generated ${sizeClass} ${artwork.gradientClass}`}>
        <span>{artwork.initials}</span>
      </div>
    );
  }

  return (
    <div className="albums-page">
      <div className="albums-hero">
        <div>
          <div className="albums-eyebrow">Library collection</div>
          <h2>Albums</h2>
          <p>Browse your albums by artwork or switch to a compact list view.</p>
        </div>

        <div className="albums-hero__stat">
          <span>{visibleAlbums.length}</span>
          <small>albums</small>
        </div>
      </div>

      <SearchBar value={searchQuery} onChange={setSearchQuery} label="albums" />

      <ViewToggle value={viewMode} options={VIEW_OPTIONS} onChange={setViewMode} />

      {viewMode === "grid" ? (
        <div className="album-grid">
          {visibleAlbums.map((album) => (
            <div key={album} className="album-card">
              <button
                className="album-card__main"
                onClick={() => goToAlbum(album)}
                type="button"
              >
                {renderArtwork(album, "album-artwork-fixed album-artwork-fixed--grid")}
                <div className="album-card__name">{album}</div>
              </button>

              <button
                className="album-card__menu-button"
                type="button"
                onClick={() => openArtworkEditor(album)}
                aria-label={`Change artwork for ${album}`}
              >
                ⋯
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="album-list">
          {visibleAlbums.map((album) => (
            <div key={album} className="album-list-row">
              <button
                className="album-list-row__main"
                onClick={() => goToAlbum(album)}
                type="button"
              >
                {renderArtwork(album, "album-artwork-fixed album-artwork-fixed--list")}
                <span className="album-list-row__name">{album}</span>
              </button>

              <button
                className="album-list-row__menu-button"
                type="button"
                onClick={() => openArtworkEditor(album)}
                aria-label={`Change artwork for ${album}`}
              >
                ⋯
              </button>
            </div>
          ))}
        </div>
      )}

      {artworkAlbum && (
        <ArtworkUploadModal
          title="Change Album Artwork"
          previewLabel={artworkAlbum}
          previewUrl={upload.previewUrl}
          fileName={upload.file?.name}
          onSelectFile={upload.selectFile}
          onSave={saveArtwork}
          onClose={closeArtworkEditor}
          isSaving={isSaving}
        />
      )}
    </div>
  );
}
