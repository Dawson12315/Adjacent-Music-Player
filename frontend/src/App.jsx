import { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { TrackListSkeleton } from "./features/library/TrackListSkeleton";
import { useAuth } from "./contexts/AuthContext";
import { AuthProvider } from "./contexts/AuthProvider";
import { LibraryProvider } from "./contexts/LibraryProvider";
import { NotificationProvider } from "./contexts/NotificationProvider";
import { PageMetaProvider } from "./contexts/PageMetaProvider";
import { PlayerProvider } from "./contexts/PlayerProvider";
import { ScanProvider } from "./contexts/ScanProvider";
import { AuthScreen } from "./features/auth/AuthScreen";
import { DuckMark } from "./components/DuckMark";

/*
 * Routes are split so the bundle is not one chunk. Settings and Insights in particular
 * are rarely opened and were previously downloaded on every visit.
 */
const HomeView = lazy(() =>
  import("./features/home/HomeView").then((m) => ({ default: m.HomeView })),
);
const TracksView = lazy(() =>
  import("./features/library/TracksView").then((m) => ({ default: m.TracksView })),
);
const ArtistsView = lazy(() =>
  import("./features/library/ArtistsView").then((m) => ({ default: m.ArtistsView })),
);
const AlbumsView = lazy(() =>
  import("./features/library/AlbumsView").then((m) => ({ default: m.AlbumsView })),
);
const GenresView = lazy(() =>
  import("./features/library/GenresView").then((m) => ({ default: m.GenresView })),
);
const PlaylistView = lazy(() =>
  import("./features/playlists/PlaylistView").then((m) => ({ default: m.PlaylistView })),
);
const InsightsView = lazy(() =>
  import("./features/insights/InsightsView").then((m) => ({ default: m.InsightsView })),
);
const SettingsView = lazy(() =>
  import("./features/settings/SettingsView").then((m) => ({ default: m.SettingsView })),
);
const LastfmCallback = lazy(() =>
  import("./features/settings/LastfmCallback").then((m) => ({ default: m.LastfmCallback })),
);

/**
 * Decides between the sign-in screen and the application, and hosts the providers the
 * application needs. Everything below the gate can assume a signed-in user.
 */
function AuthenticatedApp() {
  const { authLoading, setupRequired, currentUser } = useAuth();

  if (authLoading) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <DuckMark tile className="auth-mark" />
          <p className="auth-subtitle">Loading…</p>
        </div>
      </div>
    );
  }

  if (setupRequired) {
    return <AuthScreen mode="setup" />;
  }

  if (!currentUser) {
    return <AuthScreen mode="login" />;
  }

  return (
    <LibraryProvider>
      <ScanProvider>
        <PlayerProvider>
          <PageMetaProvider>
          <Suspense fallback={<TrackListSkeleton />}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/" element={<HomeView />} />
                <Route path="/tracks" element={<TracksView />} />

                <Route path="/artists" element={<ArtistsView />} />
                <Route path="/artists/:name" element={<TracksView />} />

                <Route path="/albums" element={<AlbumsView />} />
                <Route path="/albums/:name" element={<TracksView />} />

                <Route path="/genres" element={<GenresView />} />
                <Route path="/genres/:name" element={<TracksView />} />

                <Route path="/playlists/:playlistId" element={<PlaylistView />} />

                <Route path="/insights" element={<InsightsView />} />

                <Route path="/settings" element={<SettingsView />} />
                <Route path="/settings/lastfm/callback" element={<LastfmCallback />} />

                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
          </PageMetaProvider>
        </PlayerProvider>
      </ScanProvider>
    </LibraryProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <NotificationProvider>
        <AuthProvider>
          <AuthenticatedApp />
        </AuthProvider>
      </NotificationProvider>
    </BrowserRouter>
  );
}
