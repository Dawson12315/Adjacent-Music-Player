import { Icon } from "./Icon";

export function SearchBar({ value, onChange, label }) {
  return (
    <div style={{ position: "relative", maxWidth: 420 }}>
      <span
        style={{
          position: "absolute",
          left: 14,
          top: "50%",
          transform: "translateY(-50%)",
          color: "var(--text-muted)",
          pointerEvents: "none",
          display: "flex",
        }}
      >
        <Icon name="search" size={16} />
      </span>

      <input
        className="input input--pill"
        style={{ paddingLeft: 40, paddingRight: value ? 40 : undefined }}
        placeholder={`Search ${label}…`}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={`Search ${label}`}
      />

      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Clear search"
          style={{
            position: "absolute",
            right: 10,
            top: "50%",
            transform: "translateY(-50%)",
            color: "var(--text-muted)",
            display: "flex",
          }}
        >
          <Icon name="close" size={14} />
        </button>
      )}
    </div>
  );
}
