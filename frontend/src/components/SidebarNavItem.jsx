import { NavLink } from "react-router-dom";

import { Icon } from "./Icon";

/**
 * One navigation entry.
 *
 * A real link now, so it can be opened in a new tab, and so the browser handles focus and
 * keyboard activation. Previously six copies of a <div onClick> — two of which (Insights
 * and Settings) had no role, tabIndex or key handler at all and were unreachable by
 * keyboard.
 */
export function SidebarNavItem({ to, icon, label, end = false, onNavigate }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}
    >
      <Icon name={icon} size={18} className="nav-item__icon" />
      <span className="nav-item__label">{label}</span>
    </NavLink>
  );
}
