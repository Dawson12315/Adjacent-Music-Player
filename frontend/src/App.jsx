import { useEffect, useRef, useState } from "react";

function App() {
  const [tracks, setTracks] = useState([]);
  const [artists, setArtists] = useState([]);
  const [albums, setAlbums] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedTrack, setSelectedTrack] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeView, setActiveView] = useState("tracks");
  const [selectedArtist, setSelectedArtist] = useState(null);
  const [selectedAlbum, setSelectedAlbum] = useState(null);

  const audioRef = useRef(null);
  
  useEffect(() =>{
    async function fetchLibraryData() {
      try {
        const [tracksResponse, artistsResponse, albumsResponse] = await Promise.all([
          fetch("http://127.0.0.1:8000/api/tracks"),
          fetch("http://127.0.0.1:8000/api/artists"),
          fetch("http://127.0.0.1:8000/api/albums"),
        ])

        if (!tracksResponse.ok || !artistsResponse.ok || !albumsResponse.ok){
          throw new Error("Failed to fetch library data");
        }

        const tracksData = await tracksResponse.json();
        const artistsData = await artistsResponse.json();
        const albumsData = await albumsResponse.json();

        setTracks(tracksData);
        setArtists(artistsData);
        setAlbums(albumsData);

        if (tracksData.length > 0) {
          setSelectedTrack(tracksData[0]);
        }
      } catch (err) {
        setError("Could not load tracks.");
      } finally {
        setLoading(false);
      }
    }
    fetchLibraryData();
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
    setActiveView("tracks");
  }
  function handleArtistClick(artist) {
    setSelectedArtist(artist);
    setActiveView("tracks")
  }
  function handleAlbumClick(album) {
    setSelectedAlbum(album)
    setSelectedArtist(null)
    setActiveView("tracks")
  }
  function handleClearFilters() {
    setSelectedArtist(null);
    setSelectedAlbum(null)
    setActiveView("tracks");
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

  const visibleTracks = tracks.filter((track) => {
    if (selectedArtist) {
      return track.artist === selectedArtist
    }
    if (selectedAlbum) {
      return track.album === selectedAlbum
    }
    return true
  })

  function renderMainContent() {
    if (loading) {
      return <div className="state-message">Loading tracks...</div>
    }
    if (error) {
      return <div className="state-message">{error}</div>
    }

    if (activeView === "artists") {
      return (
        <div className="simple-list">
          {artists.map((artist) => (
            <button
              key={artist}
              className="simple-list__row simple-list__row--button"
              onClick={() => handleArtistClick(artist)}
              type="button"
            >
              {artist}
            </button>
          ))}
        </div>
      );
    }
    
    if (activeView === "albums") {
      return (
        <div className="simple-list">
          {albums.map((album) => (
            <button
              key = {album}
              className= "simple-list__row simple-list__row--button"
              onClick={() => handleAlbumClick(album)}
              type="button"
            >
              {album}
            </button>
          ))}
        </div>
      )
    }
    if (visibleTracks.length === 0) {
      return <div className="state-message">No tracks indexed yet.</div>
    }

    return (
      <div className="track-list">
        {selectedArtist && (
          <button className="filter-pill" onClick={handleClearFilters} type="button">
            Showing: {selectedArtist} ×
          </button>
        )}
        {selectedAlbum && (
          <button className="filter-pill" onClick={handleClearFilters} type= "button">
            Showing album: {selectedAlbum}
          </button>
        )}
        {visibleTracks.map((track) => (
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
    )
  }

  function getHeaderTitle() {
    if (activeView === "artists") {
      return "Artists";
    }

    if (activeView === "albums") {
      return "Albums";
    }

    if (selectedArtist) {
      return selectedArtist
    }

    if (selectedAlbum) {
      return selectedAlbum
    }

    return "Your Music"
  }

  function getHeaderSubtitle() {
    if (loading || error) {
      return "";
    }
    if (activeView === "artists") {
      return `${artists.length} artists`;
    }
    if (activeView === "albums") {
      return `${albums.length} albums`
    }

    return `${visibleTracks.length} tracks`;
  }
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar__brand">Adjacent</div>

        <nav className="sidebar__nav">
          <button 
            className={`sidebar__link ${activeView === "tracks" ? "sidebar__link--active" : ""}`}
            onClick={() => handleClearFilters()}
            type="button"
          >
            Tracks
          </button>
          <button 
            className={`sidebar__link ${activeView === "artists" ? "sidebar__link--active" : ""}`}
            onClick={() => setActiveView("artists")}
            type="button"
          >
            Artists
          </button>
          <button 
            className={`sidebar__link ${activeView === "albums" ? "sidebar__link--active" : ""}`}
            onClick={() => setActiveView("albums")}
            type="button"
          >
            Albums
          </button>
        </nav>

        <div className="sidebar__section">
          <div className="sidebar__section-title">Library</div>
          <div className="sidebar__stat">Tracks: {tracks.length}</div>
          <div className="sidebar__stat">Artists: {artists.length}</div>
          <div className="sidebar__stat">Albums: {albums.length}</div>
        </div>
      </aside>

      <main className="main-content">
        <header className="main-content__header">
          <h1>{getHeaderTitle()}</h1>
          {!loading && !error && (
            <p className="main-content__subhead">{getHeaderSubtitle()}</p>
          )}
        </header>

        <section className="main-content__body">{renderMainContent()}</section>
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

        <audio ref={audioRef} onEnded={() => setIsPlaying(false)} />
      </footer>
    </div>
  );
}

export default App;