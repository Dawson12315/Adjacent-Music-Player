import { DuckMark } from "./DuckMark";
import { SidebarNavItem } from "./SidebarNavItem";
import { PlaylistSidebarList } from "../features/playlists/PlaylistSidebarList";
import { useLibrary } from "../contexts/LibraryContext";

const PRIMARY_LINKS = [
  { to: "/", icon: "home", label: "Home", end: true },
  { to: "/tracks", icon: "tracks", label: "Tracks" },
  { to: "/artists", icon: "artists", label: "Artists" },
  { to: "/albums", icon: "albums", label: "Albums" },
  { to: "/genres", icon: "genres", label: "Genres" },
];

const SECONDARY_LINKS = [
  { to: "/insights", icon: "insights", label: "Insights" },
  { to: "/settings", icon: "settings", label: "Settings" },
];

export function Sidebar({ onNavigate }) {
  const { artists, albums, trackCount } = useLibrary();

  return (
    <aside className="sidebar">
      <div className="sidebar__header">
        <DuckMark tile className="sidebar__mark" />
        <span className="sidebar__brand">Adjacent</span>
      </div>

      <nav className="sidebar__nav" aria-label="Library">
        {PRIMARY_LINKS.map((link) => (
          <SidebarNavItem key={link.to} {...link} onNavigate={onNavigate} />
        ))}
      </nav>

      <PlaylistSidebarList onNavigate={onNavigate} />

      <nav className="sidebar__nav" aria-label="More">
        {SECONDARY_LINKS.map((link) => (
          <SidebarNavItem key={link.to} {...link} onNavigate={onNavigate} />
        ))}
      </nav>

      <div className="sidebar__section">
        <div className="sidebar__section-header">
          <span className="sidebar__section-title">Library</span>
        </div>
        <div className="sidebar__stat">
          Tracks <b>{trackCount.toLocaleString()}</b>
        </div>
        <div className="sidebar__stat">
          Artists <b>{artists.length.toLocaleString()}</b>
        </div>
        <div className="sidebar__stat">
          Albums <b>{albums.length.toLocaleString()}</b>
        </div>
      </div>
    </aside>
  );
}
