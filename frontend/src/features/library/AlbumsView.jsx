import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import { Artwork } from "../../components/Artwork";
import { ArtworkUploadModal } from "../../components/ArtworkUploadModal";
import { Icon } from "../../components/Icon";
import { ViewToggle } from "../../components/ViewToggle";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { useArtworkUpload } from "../../hooks/useArtworkUpload";
import { useInfiniteScroll } from "../../hooks/useInfiniteScroll";
import { buildAlbumPath } from "../../hooks/useNavigation";
import { uploadAlbumArtwork } from "../../services/albumsService";
import { getAlbumKey, resolveAlbumArtwork } from "../../utils/artwork";
import { useLibraryFilters } from "./useLibraryFilters";

const PAGE_SIZE = 60;

const VIEW_OPTIONS = [
  { value: "grid", label: "Grid" },
  { value: "list", label: "List" },
];

export function AlbumsView() {
  const { albumArtworkMap, setAlbumArtwork } = useLibrary();
  const { notify } = useNotifications();
  const { visibleAlbums } = useLibraryFilters();

  const [viewMode, setViewMode] = useState("grid");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [artworkAlbum, setArtworkAlbum] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  const upload = useArtworkUpload();

  /*
   * Rendered in pages. This view previously rendered every album card in one pass — 4,240
   * of them on a real library — while the tracks and artists views paginated.
   */
  const shown = visibleAlbums.slice(0, visibleCount);
  const hasMore = visibleCount < visibleAlbums.length;

  const loadMore = useCallback(() => setVisibleCount((count) => count + PAGE_SIZE), []);
  const { setSentinel } = useInfiniteScroll({ onLoadMore: loadMore, enabled: hasMore });

  function openArtworkEditor(album) {
    setArtworkAlbum(album);
    upload.setExistingArtwork(albumArtworkMap[getAlbumKey(album)]);
  }

  function closeArtworkEditor() {
    setArtworkAlbum(null);
    upload.reset();
  }

  async function saveArtwork() {
    if (!artworkAlbum || !upload.file) return;

    setIsSaving(true);

    try {
      const result = await uploadAlbumArtwork(artworkAlbum, upload.file);
      setAlbumArtwork(getAlbumKey(artworkAlbum), result.artwork_path || "");
      notify("Album artwork updated.");
      closeArtworkEditor();
    } catch (error) {
      notify(error.message || "Could not upload the album artwork.");
    } finally {
      setIsSaving(false);
    }
  }

  if (visibleAlbums.length === 0) {
    return (
      <div className="state">
        <div className="state__icon">
          <Icon name="albums" size={20} />
        </div>
        <p className="state__title">No albums found</p>
        <p className="state__text">Nothing in your library matches that search.</p>
      </div>
    );
  }

  return (
    <>
      <div className="filter-row">
        <ViewToggle value={viewMode} options={VIEW_OPTIONS} onChange={setViewMode} />
      </div>

      {viewMode === "grid" ? (
        <div className="entity-grid">
          {shown.map((album) => (
            <div key={album} className="entity-card">
              <Link to={buildAlbumPath(album)} style={{ display: "contents" }}>
                <Artwork
                  artwork={resolveAlbumArtwork(album, albumArtworkMap)}
                  className="entity-card__art"
                  size={160}
                />
                <span className="entity-card__body">
                  <span className="entity-card__name">{album}</span>
                  <span className="entity-card__meta">Album</span>
                </span>
              </Link>

              <button
                className="entity-card__menu-button"
                type="button"
                onClick={() => openArtworkEditor(album)}
                aria-label={`Change artwork for ${album}`}
              >
                <Icon name="more" size={16} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="entity-list">
          {shown.map((album) => (
            <div key={album} className="entity-row">
              <Artwork
                artwork={resolveAlbumArtwork(album, albumArtworkMap)}
                className="entity-row__art"
                size={44}
              />
              <Link to={buildAlbumPath(album)} className="entity-card__body">
                <span className="entity-row__name">{album}</span>
                <span className="entity-row__meta">Album</span>
              </Link>
              <button
                className="btn btn--icon btn--ghost btn--sm"
                type="button"
                onClick={() => openArtworkEditor(album)}
                aria-label={`Change artwork for ${album}`}
              >
                <Icon name="more" size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      {hasMore && (
        <div className="load-more" ref={setSentinel}>
          <span className="load-more__status">
            {shown.length.toLocaleString()} of {visibleAlbums.length.toLocaleString()}
          </span>
        </div>
      )}

      {artworkAlbum && (
        <ArtworkUploadModal
          title="Change album artwork"
          previewLabel={artworkAlbum}
          previewUrl={upload.previewUrl}
          fileName={upload.file?.name}
          onSelectFile={upload.selectFile}
          onSave={saveArtwork}
          onClose={closeArtworkEditor}
          isSaving={isSaving}
        />
      )}
    </>
  );
}
