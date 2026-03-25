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
  const [searchQuery, setSearchQuery]= useState("")
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

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
    setSelectedAlbum(null)
    setSearchQuery("")
    setActiveView("tracks")
  }
  function handleAlbumClick(album) {
    setSelectedAlbum(album)
    setSelectedArtist(null)
    setSearchQuery("")
    setActiveView("tracks")
  }
  function handleClearFilters() {
    setSelectedArtist(null);
    setSelectedAlbum(null)
    setSearchQuery("")
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
    const matchesArtist = selectedArtist ? track.artist === selectedArtist : true
    const matchesAlbum = selectedAlbum ? track.album === selectedAlbum : true

    const query = searchQuery.trim().toLowerCase()
    const matchesSearch =
      query === "" ||
      track.title?.toLowerCase().includes(query) ||
      track.artist?.toLowerCase().includes(query) ||
      track.album?.toLowerCase().includes(query)

    return matchesArtist && matchesAlbum && matchesSearch
  })

  const visibleArtists = artists.filter((artist) => 
    artist.toLowerCase().includes(searchQuery.trim().toLowerCase())
  )
  const visibleAlbums = albums.filter((album) =>
    album.toLowerCase().includes(searchQuery.trim().toLowerCase())
  )
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
          {visibleArtists.map((artist) => (
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
          {visibleAlbums.map((album) => (
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
      return <div className="state-message">No matching tracks found.</div>
    }

    return (
      <div className="track-list">
        {selectedArtist && (
          <button className="filter-pill" onClick={handleClearFilters} type="button">
            Showing artist: {selectedArtist} ×
          </button>
        )}
        {selectedAlbum && (
          <button className="filter-pill" onClick={handleClearFilters} type= "button">
            Showing album: {selectedAlbum} ×
          </button>
        )}
        {visibleTracks.map((track, index) => (
          <button
            key={track.id}
            className={`track-row ${
              selectedTrack?.id === track.id ? "track-row--active" : ""
            }`}
            onClick={() => handleTrackClick(track)}
            type="button"
          >
            <div className="track-row__index">{index + 1}</div>
            
            <div className="track-row__content">
              <div className="track-row__title">{track.title}</div>
              <div className="track-row__meta">
                {track.artist || "Unknown Artist"} •{" "}
                {track.album || "Unknown Album"}
              </div>
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
      return `${visibleArtists.length} artists`;
    }
    if (activeView === "albums") {
      return `${visibleAlbums.length} albums`
    }

    return `${visibleTracks.length} tracks`;
  }
  function formatTime(timeInSeconds) {
    if (!Number.isFinite(timeInSeconds)) {
      return "0:00";
    }

    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);

    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  }
  const progressPercent =
    duration > 0 ? Math.min((currentTime / duration) * 100, 100) : 0;
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
            onClick={() => {
              setActiveView("artists")
              setSearchQuery("")
            }}
            type="button"
          >
            Artists
          </button>
          <button 
            className={`sidebar__link ${activeView === "albums" ? "sidebar__link--active" : ""}`}
            onClick={() => {
              setActiveView("albums")
              setSearchQuery("")
            }}
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

        <div className="search-bar">
          <input
            className="search-input"
            placeholder={`Search ${activeView}...`}
            type="text"
            value={searchQuery}
            onChange={(event)=> setSearchQuery(event.target.value)}
          />
        </div>

        <section className="main-content__body">{renderMainContent()}</section>
      </main>

      <footer className="player-bar">
        <div className="player-bar__left">
          {selectedTrack ? (
            <>
              <div className="player-bar__title">{selectedTrack.title}</div>
              <div className="player-bar__meta">
                {selectedTrack.artist || "Unknown Artist"} •{" "}
                {selectedTrack.album || "Unknown Album"}
              </div>
            </>
          ) : (
            <div className="player-bar__meta">Nothing playing</div>
          )}
        </div>

        <div className="player-bar__center">
          <div className="player-bar__transport-row">
            <button className="player-bar__icon-button" type="button" aria-label="Shuffle">
              ↻
            </button>

            <button className="player-bar__icon-button" type="button" aria-label="Previous track">
              ⏮
            </button>

            <button
              className="player-bar__play-button"
              onClick={handlePlayPause}
              type="button"
              aria-label={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? "❚❚" : "▶"}
            </button>

            <button className="player-bar__icon-button" type="button" aria-label="Next track">
              ⏭
            </button>

            <button className="player-bar__icon-button" type="button" aria-label="Loop">
              ↺
            </button>
          </div>

          <div className="player-bar__progress-row">
            <span className="player-bar__time">{formatTime(currentTime)}</span>
            <div className="player-bar__progress-track">
              <div 
                className="player-bar__progress-fill" 
                style={{ width: `${progressPercent}%`}}
              />
            </div>
            <span className="player-bar__time">{formatTime(duration)}</span>
          </div>
        </div>

        <div className="player-bar__right" />

        <audio
          ref={audioRef}
          onEnded={() => {
            setIsPlaying(false)
            setCurrentTime(0)
          }}
          onTimeUpdate={() =>{
            if (audioRef.current) {
              setCurrentTime(audioRef.current.currentTime)
            }
          }}
          onLoadedMetadata={() => {
            if (audioRef.current) {
              setDuration(audioRef.current.duration)
            }
          }}
        />
      </footer>
    </div>
  );
}

export default App;