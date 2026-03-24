import { useEffect, useRef, useState } from "react";

function App() {
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedTrack, setSelectedTrack] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const audioRef = useRef(null);
  
  useEffect(() =>{
    async function fetchTracks() {
      try {
        const response = await fetch("http://127.0.0.1:8000/api/tracks")

        if (!response.ok) {
          throw new Error("Failed to fetch tracks");
        }

        const data = await response.json();
        setTracks(data);

        if (data.length > 0) {
          setSelectedTrack(data[0]);
        }
      } catch (err) {
        setError("Could not load tracks.");
      } finally {
        setLoading(false);
      }
    }
    fetchTracks();
  }, []);

  useEffect(() => {
    async function playSelectedTrack() {
      if (!selectedTrack || !audioRef.current) {
        return;
      }
      audioRef.current.src = `http://127.0.0.1:8000/api/tracks/${selectedTrack.id}/stream`;

      try {
        await audioRef.current.play();
        setIsPlaying(true);
      } catch (err) {
        setIsPlaying(false);
      }
    }

    playSelectedTrack();
  }, [selectedTrack]);

  function handleTrackClick(track){
    setSelectedTrack(track);
  }

  function handlePlayPause() {
    if (!audioRef.current || !selectedTrack) {
      return;
    }
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar__brand">Adjacent</div>
        <nav className="sidebar__nav">
          <button className="sidebar__link" type="button">Home</button>
          <button className="sidebar__link" type="button">Search</button>
          <button className="sidebar__link" type="button">Library</button>
        </nav>
      </aside>

      <main className="main-content">
        <header className="main-content__header">
          <h1>Your Music</h1>
          {!loading && !error && tracks.length > 0 && (
            <p className="main-content__subhead">{tracks.length} tracks</p>
          )}
        </header>

        <section className="main-content__body">
          {loading && <div className="state-message">Loading tracks...</div>}

          {!loading && error && <div className="state-message">{error}</div>}

          {!loading && !error && tracks.length === 0 && (
            <div className="state-message">No tracks indexed yet.</div>
          )}

          {!loading && !error && tracks.length > 0 && (
            <div className="track-list">
              {tracks.map((track) => (
                <button
                  key={track.id}
                  className={`track-row ${
                    selectedTrack?.id === track.id ? "track-row--active" : ""
                  }`}
                  onClick={() => handleTrackClick(track)}
                  type="button"
                >
                  <div className="track-row__title">{track.title}</div>
                  <div className="track-row__meta">
                    {track.artist || "Unknown Artist"} •{" "}
                    {track.album || "Unknown Album"}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="player-bar">
        <div className="player-bar__track">
          {selectedTrack ? (
            <>
              <div className="player-bar__title">{selectedTrack.title}</div>
              <div className="player-bar__meta">
                {selectedTrack.artist || "Unknown Artist"}
              </div>
            </>
          ) : (
            "Nothing playing"
          )}
        </div>

        <div className="player-bar__controls">
          <button onClick={handlePlayPause} type="button">
            {isPlaying ? "Pause" : "Play"}
          </button>
        </div>

        <audio
        ref={audioRef} onEnded={() => setIsPlaying(false)} />
      </footer>
    </div>
  );
}

export default App;