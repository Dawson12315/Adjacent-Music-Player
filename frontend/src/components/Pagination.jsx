export function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="pagination">
      <button
        className="pagination__button"
        type="button"
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={page === 1}
      >
        Previous
      </button>

      <span className="pagination__label">
        Page {page} of {totalPages}
      </span>

      <button
        className="pagination__button"
        type="button"
        onClick={() => onChange(Math.min(totalPages, page + 1))}
        disabled={page === totalPages}
      >
        Next
      </button>
    </div>
  );
}
