import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { useAuth } from "./contexts/AuthContext";
import { AuthProvider } from "./contexts/AuthProvider";
import { LibraryProvider } from "./contexts/LibraryProvider";
import { NotificationProvider } from "./contexts/NotificationProvider";
import { PlayerProvider } from "./contexts/PlayerProvider";
import { AuthScreen } from "./features/auth/AuthScreen";
import { AlbumsView } from "./features/library/AlbumsView";
import { ArtistsView } from "./features/library/ArtistsView";
import { GenresView } from "./features/library/GenresView";
import { TracksView } from "./features/library/TracksView";
import { InsightsView } from "./features/insights/InsightsView";
import { PlaylistView } from "./features/playlists/PlaylistView";
import { LastfmCallback } from "./features/settings/LastfmCallback";
import { SettingsView } from "./features/settings/SettingsView";

/**
 * Decides between the sign-in screen and the application, and hosts the providers the
 * application needs. Everything below the gate can assume there is a signed-in user.
 */
function AuthenticatedApp() {
  const { authLoading, setupRequired, currentUser } = useAuth();

  if (authLoading) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>Adjacent</h1>
          <p>Loading...</p>
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
      <PlayerProvider>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<TracksView />} />

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
      </PlayerProvider>
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
