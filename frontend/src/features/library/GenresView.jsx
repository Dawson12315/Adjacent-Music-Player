import { useMemo } from "react";

import { SearchBar } from "../../components/SearchBar";
import { useNavigation } from "../../hooks/useNavigation";
import { useLibraryFilters } from "./useLibraryFilters";

export function GenresView() {
  const { searchQuery, setSearchQuery, goToGenre } = useNavigation();
  const { visibleGenres, genreCounts } = useLibraryFilters();

  // Most common genres first — the ranking is the point of the view.
  const sortedGenres = useMemo(
    () =>
      [...visibleGenres].sort(
        (a, b) => (genreCounts.get(b) || 0) - (genreCounts.get(a) || 0),
      ),
    [visibleGenres, genreCounts],
  );

  const topGenre = sortedGenres[0];
  const topGenreCount = topGenre ? genreCounts.get(topGenre) || 0 : 0;

  return (
    <div className="genres-page">
      <div className="genres-hero">
        <div>
          <div className="genres-eyebrow">Library map</div>
          <h2>Genres</h2>
          <p>
            Explore your library by sound, mood, and style. Your most common genres rise
            to the top.
          </p>
        </div>

        <div className="genres-hero__stat">
          <span>{visibleGenres.length}</span>
          <small>genres</small>
        </div>
      </div>

      {topGenre && (
        <div className="genres-feature-card">
          <div>
            <div className="genres-feature-card__label">Dominant genre</div>
            <div className="genres-feature-card__title">{topGenre}</div>
            <div className="genres-feature-card__meta">
              {topGenreCount} tracks in your library
            </div>
          </div>

          <button
            className="settings-button"
            type="button"
            onClick={() => goToGenre(topGenre)}
          >
            Open genre
          </button>
        </div>
      )}

      <SearchBar value={searchQuery} onChange={setSearchQuery} label="genres" />

      <div className="genre-grid genre-grid--polished">
        {sortedGenres.map((genre, index) => (
          <button
            key={genre}
            className="genre-card genre-card--polished"
            onClick={() => goToGenre(genre)}
            type="button"
          >
            <div className="genre-card__rank">#{index + 1}</div>
            <div className="genre-card__title">{genre}</div>
            <div className="genre-card__meta">{genreCounts.get(genre) || 0} tracks</div>
          </button>
        ))}
      </div>
    </div>
  );
}
