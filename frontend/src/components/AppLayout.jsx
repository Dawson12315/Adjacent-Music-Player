import { Outlet } from "react-router-dom";

import { LibraryHeader } from "./LibraryHeader";
import { SearchBar } from "./SearchBar";
import { Sidebar } from "./Sidebar";
import { EditTrackModal } from "../features/metadata/EditTrackModal";
import { PlayerBar } from "../features/player/PlayerBar";
import { QueuePanel } from "../features/player/QueuePanel";
import { useLibrary } from "../contexts/LibraryContext";
import { usePlayer } from "../contexts/PlayerContext";
import { useNavigation } from "../hooks/useNavigation";

// Views that render their own search input inside their hero section.
const VIEWS_WITH_OWN_SEARCH = new Set(["artists", "albums", "genres", "insights", "settings"]);

export function AppLayout() {
  const { editingTrack } = useLibrary();
  const { isQueueOpen } = usePlayer();
  const { activeView, searchQuery, setSearchQuery } = useNavigation();

  return (
    <div className="app-layout">
      <Sidebar />

      <main className="main-content">
        <div className={`content-layout ${isQueueOpen ? "content-layout--queue-open" : ""}`}>
          <div className="content-layout__main">
            <LibraryHeader />

            {!VIEWS_WITH_OWN_SEARCH.has(activeView) && (
              <SearchBar value={searchQuery} onChange={setSearchQuery} label={activeView} />
            )}

            <section className="main-content__body">
              <Outlet />
            </section>
          </div>

          {isQueueOpen && <QueuePanel />}
        </div>
      </main>

      <PlayerBar />

      {editingTrack && <EditTrackModal key={editingTrack.id} />}
    </div>
  );
}
