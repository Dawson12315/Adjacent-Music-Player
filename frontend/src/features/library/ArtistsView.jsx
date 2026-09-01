import { useEffect, useState } from "react";

import { Pagination } from "../../components/Pagination";
import { SearchBar } from "../../components/SearchBar";
import { ViewToggle } from "../../components/ViewToggle";
import { useLibrary } from "../../contexts/LibraryContext";
import { useNavigation } from "../../hooks/useNavigation";
import { artworkUrl } from "../../config";
import { useLibraryFilters, usePagination } from "./useLibraryFilters";

const ARTISTS_PAGE_SIZE = 50;

const VIEW_OPTIONS = [
  { value: "list", label: "List" },
  { value: "grid", label: "Grid" },
];

export function ArtistsView() {
  const { artistArtworkMap, ensureArtistArtwork } = useLibrary();
  const { searchQuery, setSearchQuery, page, setPage, goToArtist } = useNavigation();
  const { visibleArtists } = useLibraryFilters();

  const [viewMode, setViewMode] = useState("list");

  const { pageItems, totalPages, page: safePage } = usePagination(
    visibleArtists,
    page,
    ARTISTS_PAGE_SIZE,
  );

  // Artwork is only worth fetching for the grid, which is the only view that shows it at
  // a size where it matters — matching the original behaviour.
  const signature = pageItems.join("|");

  useEffect(() => {
    if (viewMode === "grid" && pageItems.length > 0) {
      ensureArtistArtwork(pageItems);
    }
  }, [viewMode, signature, ensureArtistArtwork]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="artists-page">
      <div className="artists-hero">
        <div>
          <div className="artists-eyebrow">Library artists</div>
          <h2>Artists</h2>
          <p>Browse your collection by artist in list or visual grid view.</p>
        </div>

        <div className="artists-hero__stat">
          <span>{visibleArtists.length}</span>
          <small>artists</small>
        </div>
      </div>

      <SearchBar value={searchQuery} onChange={setSearchQuery} label="artists" />

      <ViewToggle value={viewMode} options={VIEW_OPTIONS} onChange={setViewMode} />

      {viewMode === "list" ? (
        <div className="artist-list">
          {pageItems.map((artist) => (
            <button
              key={artist}
              className="artist-list-row"
              onClick={() => goToArtist(artist)}
              type="button"
            >
              <div className="artist-list-row__avatar">
                {artistArtworkMap[artist] ? (
                  <img
                    className="artist-list-row__img"
                    src={artworkUrl(artistArtworkMap[artist])}
                    alt=""
                  />
                ) : (
                  <span>{artist.slice(0, 1).toUpperCase()}</span>
                )}
              </div>

              <div className="artist-list-row__content">
                <div className="artist-list-row__name">{artist}</div>
                <div className="artist-list-row__meta">Artist</div>
              </div>

              <div className="artist-list-row__arrow">›</div>
            </button>
          ))}
        </div>
      ) : (
        <div className="artist-grid artist-grid--polished">
          {pageItems.map((artist) => (
            <button
              key={artist}
              className="artist-grid-card"
              onClick={() => goToArtist(artist)}
              type="button"
            >
              <div className="artist-grid-card__image">
                {artistArtworkMap[artist] ? (
                  <img
                    className="artist-grid-card__img"
                    src={artworkUrl(artistArtworkMap[artist])}
                    alt=""
                  />
                ) : (
                  <span>{artist.slice(0, 1).toUpperCase()}</span>
                )}
              </div>

              <div className="artist-grid-card__name">{artist}</div>
              <div className="artist-grid-card__meta">Artist</div>
            </button>
          ))}
        </div>
      )}

      <Pagination page={safePage} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
