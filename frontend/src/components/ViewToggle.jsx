export function ViewToggle({ value, options, onChange }) {
  return (
    <div className="view-toggle">
      {options.map((option) => (
        <button
          key={option.value}
          className={`view-toggle__button ${
            value === option.value ? "view-toggle__button--active" : ""
          }`}
          type="button"
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
