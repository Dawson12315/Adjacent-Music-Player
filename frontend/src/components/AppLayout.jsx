import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";

import { Icon } from "./Icon";
import { PageHeader } from "./PageHeader";
import { SearchBar } from "./SearchBar";
import { Sidebar } from "./Sidebar";
import { EditTrackModal } from "../features/metadata/EditTrackModal";
import { PlayerBar } from "../features/player/PlayerBar";
import { QueuePanel } from "../features/player/QueuePanel";
import { useLibrary } from "../contexts/LibraryContext";
import { useNotifications } from "../contexts/NotificationContext";
import { usePlayer } from "../contexts/PlayerContext";
import { useNavigation } from "../hooks/useNavigation";

/** Views that browse a list and want the shared search field above them. */
const SEARCHABLE_VIEWS = new Set(["tracks", "artists", "albums", "genres", "playlist"]);

export function AppLayout() {
  const { editingTrack } = useLibrary();
  const { isQueueOpen } = usePlayer();
  const { notice } = useNotifications();
  const { activeView, searchQuery, setSearchQuery } = useNavigation();

  // Every sidebar link calls onNavigate, which is how the drawer closes behind you on
  // mobile — driven by the interaction rather than by watching the location.
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const closeDrawer = useCallback(() => setIsDrawerOpen(false), []);

  return (
    <div className={`app-layout ${isDrawerOpen ? "app-layout--drawer-open" : ""}`}>
      <button
        className="drawer-toggle"
        type="button"
        aria-label="Open navigation"
        aria-expanded={isDrawerOpen}
        onClick={() => setIsDrawerOpen((open) => !open)}
      >
        <Icon name="menu" size={20} />
      </button>

      {isDrawerOpen && (
        <div
          className="sidebar__scrim"
          onClick={closeDrawer}
          role="presentation"
        />
      )}

      <Sidebar onNavigate={closeDrawer} />

      <main className="main-content">
        <div className={`content-layout ${isQueueOpen ? "content-layout--queue-open" : ""}`}>
          <div className="content-layout__main">
            <PageHeader />

            {SEARCHABLE_VIEWS.has(activeView) && (
              <div className="search-bar">
                <SearchBar
                  value={searchQuery}
                  onChange={setSearchQuery}
                  label={activeView}
                />
              </div>
            )}

            <section className="main-content__body">
              <Outlet />
            </section>
          </div>

          {isQueueOpen && <QueuePanel />}
        </div>
      </main>

      <PlayerBar />

      {/* One live region for app-level notices */}
      <div aria-live="polite" className="visually-hidden">
        {notice}
      </div>

      {editingTrack && <EditTrackModal key={editingTrack.id} />}
    </div>
  );
}
