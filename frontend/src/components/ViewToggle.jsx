export function ViewToggle({ value, options, onChange }) {
  return (
    <div className="view-toggle" role="group" aria-label="View mode">
      {options.map((option) => (
        <button
          key={option.value}
          className={`view-toggle__button ${
            value === option.value ? "view-toggle__button--active" : ""
          }`}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
