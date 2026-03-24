import { useEffect, useState } from "react";

function App() {
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  
  useEffect(() =>{
    async function fetchTracks() {
      try {
        const response = await fetch("http://127.0.0.1:8000/api/tracks")

        if (!response.ok) {
          throw new Error("Failed to fetch tracks");
        }

        const data = await response.json();
        setTracks(data);
      } catch (err) {
        setError("Could not load tracks.");
      } finally {
        setLoading(false);
      }
    }
    fetchTracks();
  }, []);
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar__brand">Adjacent</div>
        <nav className="sidebar__nav">
          <button className="sidebar__link">Home</button>
          <button className="sidebar__link">Search</button>
          <button className="sidebar__link">Library</button>
        </nav>
      </aside>

      <main className="main-content">
        <header className="main-content__header">
          <h1>Your Music</h1>
        </header>

        <section className="main-content__body">
          {loading && <p>Loading tracks...</p>}
          {error && <p>{error}</p>}

          {!loading && !error && (
            <div className="track-list">
              {tracks.map((track) => (
                <div key={track.id} className="track-row">
                  <div className="track-row__title">{track.title}</div>
                  <div className="track-row__meta">
                    {track.artist || "Unknown Artist"} • {track.album || "Unknown Album"}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="player-bar">
        <div className="player-bar__track">Nothing playing</div>
        <div className="player-bar__controls">
          <button>Play</button>
        </div>
      </footer>
    </div>
  );
}

export default App;