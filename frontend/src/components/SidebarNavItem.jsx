/**
 * One navigation entry in the sidebar.
 *
 * The same block was repeated six times with its handlers inlined twice each, once for
 * click and once for key press. Two of the six — Insights and Settings — were bare divs
 * with only a click handler, so they were unreachable by keyboard; extracting the
 * component gives all six the treatment the others already had.
 */
export function SidebarNavItem({ label, imageSrc, isActive, onActivate }) {
  return (
    <div
      className={`playlist-sidebar-item__main ${isActive ? "sidebar__link--active" : ""}`}
      onClick={onActivate}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onActivate();
        }
      }}
    >
      <div className="playlist-art-wrapper">
        <img className="playlist-art" src={imageSrc} alt="" />
      </div>

      <button
        className="playlist-sidebar-item__name-button"
        type="button"
        aria-current={isActive ? "page" : undefined}
      >
        {label}
      </button>
    </div>
  );
}
