/**
 * The search input was pasted into four views because the shared one was hidden for
 * them; this is that one component.
 */
export function SearchBar({ value, onChange, label }) {
  return (
    <div className="search-bar">
      <input
        className="search-input"
        placeholder={`Search ${label}...`}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={`Search ${label}`}
      />
    </div>
  );
}
