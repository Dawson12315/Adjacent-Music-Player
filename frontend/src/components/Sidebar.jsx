import { useNavigate } from "react-router-dom";

import { SidebarNavItem } from "./SidebarNavItem";
import { PlaylistSidebarList } from "../features/playlists/PlaylistSidebarList";
import { useLibrary } from "../contexts/LibraryContext";
import { useNavigation } from "../hooks/useNavigation";

const PRIMARY_LINKS = [
  { view: "tracks", path: "/", label: "Tracks", image: "/tracks.png" },
  { view: "artists", path: "/artists", label: "Artists", image: "/artists.png" },
  { view: "albums", path: "/albums", label: "Albums", image: "/albums.png" },
  { view: "genres", path: "/genres", label: "Genres", image: "/genre.png" },
];

const SECONDARY_LINKS = [
  { view: "insights", path: "/insights", label: "Insights", image: "/insights.png" },
  { view: "settings", path: "/settings", label: "Settings", image: "/settings.png" },
];

export function Sidebar() {
  const navigate = useNavigate();
  const { tracks, artists, albums } = useLibrary();
  const { activeView, selectedArtist, selectedAlbum, selectedGenre } = useNavigation();

  // The library link is only "active" when nothing is filtered, matching the old
  // behaviour where clearing filters was what made it highlight.
  const isLibraryActive =
    activeView === "tracks" && !selectedArtist && !selectedAlbum && !selectedGenre;

  return (
    <aside className="sidebar">
      <div className="sidebar__header">
        <img className="logo" src="/Adjacent.svg" alt="Adjacent logo" />
        <div className="sidebar__brand">Adjacent</div>
      </div>

      <nav className="sidebar__nav">
        {PRIMARY_LINKS.map(({ view, path, label, image }) => (
          <SidebarNavItem
            key={view}
            label={label}
            imageSrc={image}
            isActive={view === "tracks" ? isLibraryActive : activeView === view}
            onActivate={() => navigate(path)}
          />
        ))}
      </nav>

      <PlaylistSidebarList />

      {SECONDARY_LINKS.map(({ view, path, label, image }) => (
        <div className="sidebar__section" key={view}>
          <SidebarNavItem
            label={label}
            imageSrc={image}
            isActive={activeView === view}
            onActivate={() => navigate(path)}
          />
        </div>
      ))}

      <div className="sidebar__section">
        <div className="sidebar__section-title">Library</div>
        <div className="sidebar__stat">Tracks: {tracks.length}</div>
        <div className="sidebar__stat">Artists: {artists.length}</div>
        <div className="sidebar__stat">Albums: {albums.length}</div>
      </div>
    </aside>
  );
}
