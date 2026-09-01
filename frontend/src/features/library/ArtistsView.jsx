import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import { Artwork } from "../../components/Artwork";
import { Icon } from "../../components/Icon";
import { ViewToggle } from "../../components/ViewToggle";
import { useLibrary } from "../../contexts/LibraryContext";
import { useInfiniteScroll } from "../../hooks/useInfiniteScroll";
import { buildArtistPath } from "../../hooks/useNavigation";
import { resolveArtistArtwork } from "../../utils/artwork";
import { useLibraryFilters } from "./useLibraryFilters";

const PAGE_SIZE = 60;

const VIEW_OPTIONS = [
  { value: "grid", label: "Grid" },
  { value: "list", label: "List" },
];

export function ArtistsView() {
  const { artistArtworkMap } = useLibrary();
  const { visibleArtists } = useLibraryFilters();

  const [viewMode, setViewMode] = useState("grid");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  // 992 artists is small enough to hold, but not to render at once.
  const shown = visibleArtists.slice(0, visibleCount);
  const hasMore = visibleCount < visibleArtists.length;

  const loadMore = useCallback(() => {
    setVisibleCount((count) => count + PAGE_SIZE);
  }, []);

  const { setSentinel } = useInfiniteScroll({ onLoadMore: loadMore, enabled: hasMore });

  if (visibleArtists.length === 0) {
    return (
      <div className="state">
        <div className="state__icon">
          <Icon name="artists" size={20} />
        </div>
        <p className="state__title">No artists found</p>
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
          {shown.map((artist) => (
            <Link key={artist} to={buildArtistPath(artist)} className="entity-card">
              <Artwork
                artwork={resolveArtistArtwork(artist, artistArtworkMap)}
                className="entity-card__art entity-card__art--round"
                size={160}
              />
              <span className="entity-card__body">
                <span className="entity-card__name">{artist}</span>
                <span className="entity-card__meta">Artist</span>
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <div className="entity-list">
          {shown.map((artist) => (
            <Link key={artist} to={buildArtistPath(artist)} className="entity-row">
              <Artwork
                artwork={resolveArtistArtwork(artist, artistArtworkMap)}
                className="entity-row__art entity-row__art--round"
                size={44}
              />
              <span className="entity-card__body">
                <span className="entity-row__name">{artist}</span>
                <span className="entity-row__meta">Artist</span>
              </span>
              <Icon name="chevronRight" size={16} className="entity-row__chevron" />
            </Link>
          ))}
        </div>
      )}

      {hasMore && (
        <div className="load-more" ref={setSentinel}>
          <span className="load-more__status">
            {shown.length.toLocaleString()} of {visibleArtists.length.toLocaleString()}
          </span>
        </div>
      )}
    </>
  );
}
