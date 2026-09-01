import { Link } from "react-router-dom";

import { Icon } from "../../components/Icon";
import { buildGenrePath } from "../../hooks/useNavigation";
import { getTone } from "../../utils/artwork";
import { useLibraryFilters } from "./useLibraryFilters";

export function GenresView() {
  const { visibleGenres } = useLibraryFilters();

  if (visibleGenres.length === 0) {
    return (
      <div className="state">
        <div className="state__icon">
          <Icon name="genres" size={20} />
        </div>
        <p className="state__title">No genres found</p>
        <p className="state__text">
          Genres come from file tags and Last.fm enrichment. Run a scan, or connect
          Last.fm from Settings, to fill them in.
        </p>
      </div>
    );
  }

  return (
    <div className="genre-grid">
      {visibleGenres.map((genre) => (
        <Link
          key={genre}
          to={buildGenrePath(genre)}
          className={`genre-card genre-card--${getTone(genre)}`}
        >
          <span className="genre-card__title">{genre}</span>
        </Link>
      ))}
    </div>
  );
}
