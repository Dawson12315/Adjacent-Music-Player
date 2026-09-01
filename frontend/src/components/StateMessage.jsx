import { Icon } from "./Icon";

/**
 * One state treatment for empty, loading and error. There were five before — a solid
 * card, two dashed variants in different colours, and two more that had no CSS at all.
 */
export function StateMessage({ icon = "music", title, children, tone }) {
  return (
    <div className={`state ${tone === "error" ? "state--error" : ""}`}>
      <div className="state__icon">
        <Icon name={icon} size={20} />
      </div>
      {title && <p className="state__title">{title}</p>}
      {children && <p className="state__text">{children}</p>}
    </div>
  );
}
