import { useEffect, useMemo, useRef, useState } from "react";

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
  const [isShuffle, setIsShuffle] = useState(false);
  const [isLoop, setIsLoop] = useState(false);
  const [shuffleHistory, setShuffleHistory] = useState([]);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [queue, setQueue] = useState([]);
  const [queueIndex, setQueueIndex] = useState(-1);
  const [openMenuTrackId, setOpenMenuTrackId] = useState(null);
  const [isQueueOpen, setIsQueueOpen] = useState(false);
  const [originalQueue, setOriginalQueue] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [newPlaylistName, setNewPlaylistName] = useState("");
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [playlistTracks, setPlaylistTracks] = useState([]);
  const [openPlaylistMenuId, setOpenPlaylistMenuId] = useState(null);
  const [editingPlaylistId, setEditingPlaylistId] = useState(null);
  const [editingPlaylistName, setEditingPlaylistName] = useState("");
  const [isCreatingPlaylist, setIsCreatingPlaylist] = useState(false);
  const [hasRestoredPlayback, setHasRestoredPlayback] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [settingsNotice, setSettingsNotice] = useState("");
  const [appSettings, setAppSettings] = useState({
    cleanup_enabled: false,
    cleanup_time: "",
    scan_enabled: false,
    scan_time: "",
  });
  const [tracksPage, setTracksPage] = useState(1);
  const [artistsPage, setArtistsPage] = useState(1);
  const [isScanningLibrary, setIsScanningLibrary] = useState(false);
  const [likedSongsPlaylist, setLikedSongsPlaylist] = useState(null);
  const [isCurrentTrackLiked, setIsCurrentTrackLiked] = useState(false);
  const [editingTrack, setEditingTrack] = useState(null);
  const [editTrackTitle, setEditTrackTitle] = useState("");
  const [editTrackArtist, setEditTrackArtist] = useState("");
  const [editTrackAlbum, setEditTrackAlbum] = useState("");
  const [isArtistMenuOpen, setIsArtistMenuOpen] = useState(false);
  const [isCreatingArtist, setIsCreatingArtist] = useState(false);
  const [newArtistName, setNewArtistName] = useState("");
  const [isAlbumMenuOpen, setIsAlbumMenuOpen] = useState(false);
  const [isCreatingAlbum, setIsCreatingAlbum] = useState(false);
  const [newAlbumName, setNewAlbumName] = useState("");
  const [isArtistActionsOpen, setIsArtistActionsOpen] = useState(false);
  const [editingArtistName, setEditingArtistName] = useState("");
  const [transferArtistTarget, setTransferArtistTarget] = useState("");
  const [isEditArtistModalOpen, setIsEditArtistModalOpen] = useState(false);
  const [isTransferArtistMenuOpen, setIsTransferArtistMenuOpen] = useState(false);
  const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || "http://127.0.0.1:8000";

  const TRACKS_PAGE_SIZE = 50;
  const ARTISTS_PAGE_SIZE = 50;

  const audioRef = useRef(null);
  const progressBarRef = useRef(null)
  const pendingSeekRef = useRef(null)
  
  useEffect(() =>{
    async function fetchLibraryData() {
      try {
        const [
          tracksResponse,
          artistsResponse,
          albumsResponse,
          playlistsResponse,
          settingsResponse,
          likedSongsPlaylistResponse
        ] = await Promise.all([
          fetch(`${API_BASE_URL}/api/tracks`),
          fetch(`${API_BASE_URL}/api/artists`),
          fetch(`${API_BASE_URL}/api/albums`),
          fetch(`${API_BASE_URL}/api/playlists`),
          fetch(`${API_BASE_URL}/api/settings`),
          fetch(`${API_BASE_URL}/api/playlists/liked-songs`)
        ])

        if (
          !tracksResponse.ok ||
          !artistsResponse.ok ||
          !albumsResponse.ok ||
          !playlistsResponse.ok ||
          !settingsResponse.ok ||
          !likedSongsPlaylistResponse.ok
        ){
          throw new Error("Failed to fetch library data");
        }

        const tracksData = await tracksResponse.json();
        const artistsData = await artistsResponse.json();
        const albumsData = await albumsResponse.json();
        const playlistsData = await playlistsResponse.json();
        const settingsData = await settingsResponse.json()
        const likedSongsPlaylistData = await likedSongsPlaylistResponse.json();

        setTracks(tracksData);
        setArtists(artistsData);
        setAlbums(albumsData);
        setPlaylists(
          [...playlistsData].sort((a, b) => {
            if (a.system_key === "liked_songs") return -1
            if (b.system_key === "liked_songs") return 1
            return a.name.localeCompare(b.name)
          })
        )
        setAppSettings({
          cleanup_enabled: settingsData.cleanup_enabled,
          cleanup_time: settingsData.cleanup_time || "",
          scan_enabled: settingsData.scan_enabled,
          scan_time: settingsData.scan_time || "",
        })
        setLikedSongsPlaylist(likedSongsPlaylistData);

        // Restore playback state
        const playbackResponse = await fetch(`${API_BASE_URL}/api/playback`);

        if (playbackResponse.ok) {
          const playbackData = await playbackResponse.json();
        
          const {
            current_track_id,
            queue_index,
            current_time_seconds,
            is_playing,
            is_shuffle,
            is_loop,
            queue_track_ids,
          } = playbackData;
        
          // rebuild queue from track IDs
          const trackMap = new Map(tracksData.map((track) => [track.id, track]));
        
          const restoredQueue = queue_track_ids
            .map((id) => trackMap.get(id))
            .filter(Boolean);
        
          setQueue(restoredQueue);
          setOriginalQueue(restoredQueue);
          setQueueIndex(queue_index);
          setIsShuffle(is_shuffle);
          setIsLoop(is_loop)
        
          let restoredTrack = null;

          if (restoredQueue.length > 0 && queue_index >= 0 && restoredQueue[queue_index]) {
            restoredTrack = restoredQueue[queue_index];
          } else if (current_track_id) {
            restoredTrack = trackMap.get(current_track_id) || null;
          }

          setSelectedTrack(restoredTrack);
        
          if (Number.isFinite(current_time_seconds)) {
            setCurrentTime(current_time_seconds);
            pendingSeekRef.current = current_time_seconds
          }
          setIsPlaying(is_playing);
        }
      } catch (err) {
        setError("Could not load tracks.");
      } finally {
        setHasRestoredPlayback(true);
        setLoading(false);
      }
    }
    fetchLibraryData();
  }, []);

  useEffect(() => {
    if (!selectedTrack || !audioRef.current) {
      return;
    }
  
    audioRef.current.src = `${API_BASE_URL}/api/tracks/${selectedTrack.id}/stream`;
    audioRef.current.load();
  }, [selectedTrack]);

  useEffect(() => {
    if (!audioRef.current || !selectedTrack) {
      return;
    }

    if (isPlaying) {
      audioRef.current.play().catch(() => {
        setIsPlaying(false);
      });
    } else {
      audioRef.current.pause();
    }
  }, [isPlaying, selectedTrack]);

  useEffect(() => {
    if (!audioRef.current) {
      return
    }
    audioRef.current.volume = volume
    audioRef.current.muted = isMuted
  }, [volume, isMuted])

  function getPlaybackSourceTracks() {
    if (activeView === "playlist" && selectedPlaylist) {
      return playlistTracks;
    }

    return visibleTracks;
  }

  useEffect(() => {
    if (!settingsNotice) {
      return;
    }

    const timeout = setTimeout(() => {
      setSettingsNotice("");
    }, 5000);

    return () => clearTimeout(timeout);
  }, [settingsNotice]);

  useEffect(() => {
    if (!hasRestoredPlayback) {
      return;
    }

    async function savePlaybackState() {
      const queueTrackIds = queue.map((track) => track.id);

      try {
        await fetch(`${API_BASE_URL}/api/playback`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            current_track_id: selectedTrack ? selectedTrack.id : null,
            queue_index: queueIndex,
            current_time_seconds: Math.floor(currentTime),
            is_playing: isPlaying,
            is_shuffle: isShuffle,
            is_loop: isLoop,
            queue_track_ids: queueTrackIds,
          }),
        });
      } catch (error) {
        console.error("Failed to save playback state", error);
      }
    }

    savePlaybackState();
  }, [
    hasRestoredPlayback,
    selectedTrack,
    queue,
    queueIndex,
    isPlaying,
    isShuffle,
    isLoop,
  ]);

  useEffect(() => {
    if (!hasRestoredPlayback) {
      return;
    }

    if (isPlaying) {
      return;
    }

    async function savePlaybackTime() {
      try {
        await fetch(`${API_BASE_URL}/api/playback`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            current_track_id: selectedTrack ? selectedTrack.id : null,
            queue_index: queueIndex,
            current_time_seconds: Math.floor(currentTime),
            is_playing: isPlaying,
            is_shuffle: isShuffle,
            is_loop: isLoop,
            queue_track_ids: queue.map((track) => track.id),
          }),
        });
      } catch (error) {
        console.error("Failed to save playback time", error);
      }
    }

    savePlaybackTime();
  }, [
    hasRestoredPlayback,
    currentTime,
    isPlaying,
    selectedTrack,
    queue,
    queueIndex,
    isShuffle,
    isLoop,
  ]);

  useEffect(() => {
    setTracksPage(1);
  }, [searchQuery, selectedArtist, selectedAlbum, activeView]);
  
  useEffect(() => {
    setArtistsPage(1);
  }, [searchQuery, activeView]);

  useEffect(() => {
    async function fetchLikedState() {
      if (!selectedTrack) {
        setIsCurrentTrackLiked(false);
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/playlists/liked-songs/tracks/${selectedTrack.id}`
        );

        if (!response.ok) {
          throw new Error("Failed to check liked state");
        }

        const data = await response.json();
        setIsCurrentTrackLiked(data.liked);
      } catch (error) {
        console.error(error);
        setIsCurrentTrackLiked(false);
      }
    }

    fetchLikedState();
  }, [selectedTrack]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) {
      return;
    }

    navigator.mediaSession.setActionHandler("play", async () => {
      if (!audioRef.current || !selectedTrack) {
        return;
      }

      try {
        await audioRef.current.play();
      } catch (error) {
        console.error(error);
      }
    });

    navigator.mediaSession.setActionHandler("pause", () => {
      if (!audioRef.current) {
        return;
      }

      audioRef.current.pause();
    });

    navigator.mediaSession.setActionHandler("previoustrack", () => {
      handlePreviousTrack();
    });

    navigator.mediaSession.setActionHandler("nexttrack", () => {
      handleNextTrack();
    });

    return () => {
      navigator.mediaSession.setActionHandler("play", null);
      navigator.mediaSession.setActionHandler("pause", null);
      navigator.mediaSession.setActionHandler("previoustrack", null);
      navigator.mediaSession.setActionHandler("nexttrack", null);
    };
  }, [selectedTrack, queue, queueIndex, isLoop, isShuffle]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) {
      return;
    }

    if (!selectedTrack) {
      navigator.mediaSession.metadata = null;
      return;
    }

    navigator.mediaSession.metadata = new MediaMetadata({
      title: selectedTrack.title || "Unknown Title",
      artist: selectedTrack.artist || "Unknown Artist",
      album: selectedTrack.album || "Unknown Album",
    });
  }, [selectedTrack]);

  function handleTrackClick(track){
    setOpenMenuTrackId(null)
    setSelectedTrack(track);

    const sourceTracks = getPlaybackSourceTracks()
    const clickedIndex = sourceTracks.findIndex((item) => item.id === track.id)

    const nextOriginalQueue = [...sourceTracks]
    const beforeCurrent = nextOriginalQueue.slice(0, clickedIndex + 1)
    const upcoming = nextOriginalQueue.slice(clickedIndex + 1)

    const nextQueue = isShuffle
      ? [...beforeCurrent, ...shuffleItems(upcoming)]
      : nextOriginalQueue;

    setOriginalQueue(nextOriginalQueue)
    setQueue(nextQueue)
    setQueueIndex(clickedIndex)

    if (activeView !== "playlist") {
      setActiveView("tracks")
    }
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
  function handleAddToQueue(track) {
  setQueue((prev) => [...prev, track]);
  setOriginalQueue((prev) => [...prev,track])
  setOpenMenuTrackId(null)
  }
  function handleToggleQueue() {
  setIsQueueOpen((prev) => !prev);
  }
  function handleToggleMute() {
    setIsMuted((prev) => !prev)
  }
  function handleVolumeChange(event) {
    const newVolume = Number(event.target.value)
    setVolume(newVolume)

    if (newVolume > 0 && isMuted) {
      setIsMuted(false)
    }
    if (newVolume === 0){
      setIsMuted(true)
    }
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

  function handlePreviousTrack() {
    if (!selectedTrack || !audioRef.current || queue.length === 0) {
      return;
    }

    if (audioRef.current.currentTime > 5) {
      audioRef.current.currentTime = 0
      setCurrentTime(0)
      return
    }

    if (isShuffle && shuffleHistory.length > 0) {
      const previousIndex = shuffleHistory[shuffleHistory.length - 1]

      setShuffleHistory((prev) => prev.slice(0, -1))
      setQueueIndex(previousIndex)
      setSelectedTrack(queue[previousIndex])
      return
    }

    if (queueIndex <= 0) {
      audioRef.current.currentTime = 0
      setCurrentTime(0)
      return
    }
    const prevIndex = queueIndex -1
    setQueueIndex(prevIndex)
    setSelectedTrack(queue[prevIndex]);
  }

  function handleNextTrack() {
    if (!queue.length || queueIndex === -1) {
      return;
    }
    if (queueIndex >= queue.length -1) {
      return
    }
      const nextIndex = queueIndex + 1
      setQueueIndex(nextIndex)
      setSelectedTrack(queue[nextIndex])
      return
  }
  
  function handleToggleShuffle() {
    setIsShuffle((prevIsShuffle) => {
        const nextIsShuffle = !prevIsShuffle;
    
        if (queue.length === 0 || queueIndex < 0) {
          return nextIsShuffle;
        }
      
        if (nextIsShuffle) {
          setQueue((prevQueue) => {
            const beforeCurrent = prevQueue.slice(0, queueIndex + 1);
            const upcoming = prevQueue.slice(queueIndex + 1);
          
            return [...beforeCurrent, ...shuffleItems(upcoming)];
          });
        } else {
          setQueue(() => {
            const currentTrack = queue[queueIndex];
          
            if (!currentTrack) {
              return originalQueue;
            }
          
            const restoredIndex = originalQueue.findIndex(
              (track) => track.id === currentTrack.id
            );
          
            if (restoredIndex === -1) {
              return originalQueue;
            }
          
            setQueueIndex(restoredIndex);
            return originalQueue;
          });
        }
      
        return nextIsShuffle;
    })
  }
  function shuffleItems(items) {
    const shuffled = [...items];
    
    for (let index = shuffled.length - 1; index > 0; index -= 1) {
      const randomIndex = Math.floor(Math.random() * (index + 1));
      [shuffled[index], shuffled[randomIndex]] = [
        shuffled[randomIndex],
        shuffled[index],
      ];
    }

    return shuffled;
  }

  function handleToggleLoop() {
    setIsLoop((prev) => !prev);
  }
  function handleRemoveFromQueue(indexToRemove) {
    const trackToRemove = queue[indexToRemove]
    if (!trackToRemove) {
      return
    }

    setQueue((prevQueue) => prevQueue.filter((_, index) => index !== indexToRemove));

    setOriginalQueue((prevOriginalQueue) => {
      const originalIndex = prevOriginalQueue.findIndex(
        (track, index) =>
          index >= queueIndex &&
          track.id === trackToRemove.id
    )
    if (originalIndex === -1) {
      return prevOriginalQueue
    }
    return prevOriginalQueue.filter((_, index) => index !== originalIndex)
    })
    if (indexToRemove < queueIndex) {
      setQueueIndex((prevIndex) => prevIndex - 1);
      return;
    }

    if (indexToRemove === queueIndex) {
      const nextQueueLength = queue.length - 1;

      if (nextQueueLength <= 0) {
        setQueueIndex(-1);
        setSelectedTrack(null);
        setIsPlaying(false);

        if (audioRef.current) {
          audioRef.current.pause();
        }
        return;
      }

      const nextIndex = Math.min(queueIndex, nextQueueLength - 1);
      setQueueIndex(nextIndex);
      setSelectedTrack(queue[nextIndex === indexToRemove ? nextIndex + 1 : nextIndex] || null);
    }
  }
  function playNextAvailableTrack() {
    if (!queue.length || queueIndex === -1) {
      setIsPlaying(false);
      return;
    }

    if(queueIndex >= queue.length -1) {
      setIsPlaying(false)
      return
    }
    const nextIndex = queueIndex + 1
    setQueueIndex(nextIndex)
    setSelectedTrack(queue[nextIndex])
  }
  function handleSeek(event) {
    if (!audioRef.current || !progressBarRef.current || duration <= 0) {
     return;
    }

    const rect = progressBarRef.current.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const ratio = Math.min(Math.max(clickX / rect.width, 0), 1);
    const newTime = ratio * duration;

    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  }
  async function handleCreatePlaylist() {
    const trimmedName = newPlaylistName.trim();

    if (!trimmedName) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/playlists`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: trimmedName }),
      });

      if (!response.ok) {
        throw new Error("Failed to create playlist");
      }

      const createdPlaylist = await response.json();

      setPlaylists((prev) => 
        [...prev, createdPlaylist].sort((a, b) => {
          if (a.system_key === "liked_songs") return -1
          if (b.system_key === "liked_songs") return 1
          return a.name.localeCompare(b.name)
        })
      )
      setNewPlaylistName("");
      setIsCreatingPlaylist(false)
    } catch (error) {
      console.error(error);
    }
  }

  async function handleAddTrackToPlaylist(trackId, playlistId) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${playlistId}/tracks`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ track_id: trackId }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to add track to playlist");
      }

      setOpenMenuTrackId(null);
    } catch (error) {
      console.error(error);
    }
  }
  async function handleRemoveTrackFromPlaylist(trackId) {
    if (!selectedPlaylist) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${selectedPlaylist.id}/tracks/${trackId}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error("Failed to remove track from playlist");
      }

      setPlaylistTracks((prev) => prev.filter((track) => track.id !== trackId));
      setOpenMenuTrackId(null);
    } catch (error) {
      console.error(error);
    }
  }
  async function handlePlaylistClick(playlist) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${playlist.id}/tracks`
      );

      if (!response.ok) {
        throw new Error("Failed to fetch playlist tracks");
      }

      const tracksData = await response.json();

      setSelectedPlaylist(playlist);
      setPlaylistTracks(tracksData);
      setSelectedArtist(null);
      setSelectedAlbum(null);
      setSearchQuery("");
      setActiveView("playlist");
    } catch (error) {
      console.error(error);
    }
  }
  async function handleDeletePlaylist(playlistId) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${playlistId}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error("Failed to delete playlist");
      }

      setPlaylists((prev) => prev.filter((playlist) => playlist.id !== playlistId));

      if (selectedPlaylist?.id === playlistId) {
        setSelectedPlaylist(null);
        setPlaylistTracks([]);
        setActiveView("tracks");
      }

      setOpenPlaylistMenuId(null);
    } catch (error) {
      console.error(error);
    }
  }

  function handleStartRenamePlaylist(playlist) {
    setEditingPlaylistId(playlist.id)
    setEditingPlaylistName(playlist.name)
    setOpenPlaylistMenuId(null)
  }

  async function handleSubmitRenamePlaylist(playlistId) {
    const trimmedName = editingPlaylistName.trim()

    if (!trimmedName) {
      setEditingPlaylistId(null)
      setEditingPlaylistName("")
      return
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${playlistId}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ name: trimmedName }),
        }
      )
      if (!response.ok) {
        throw new Error("Failed to rename playlist")
      }
      const updatedPlaylist = await response.json()

      setPlaylists((prev) =>
        prev
          .map((item) =>
            item.id === updatedPlaylist.id ? updatedPlaylist: item
          )
          .sort((a,b) => {
            if (a.system_key === "liked_songs") return -1
            if (b.system_key === "liked_songs") return 1
            return a.name.localeCompare(b.name)
          })
      )

      if (selectedPlaylist?.id === updatedPlaylist.id) {
        setSelectedPlaylist(updatedPlaylist)
      }
    } catch (error) {
      console.error(error)
    } finally {
      setEditingPlaylistId(null)
      setEditingPlaylistName("")
    }
  }

  function handleCancelRenamePlaylist() {
    setEditingPlaylistId(null)
    setEditingPlaylistName("")
  }

  async function handlePurgeTracks() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tracks/purge`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("Failed to purge tracks");
      }

      setTracks([]);
      setPlaylistTracks([]);
      setQueue([]);
      setOriginalQueue([]);
      setQueueIndex(-1);
      setSelectedTrack(null);
      setCurrentTime(0);
      setDuration(0);
      setIsPlaying(false);
      setSelectedArtist(null);
      setSelectedAlbum(null);

      setConfirmAction(null);
      setSettingsNotice("Stored tracks were purged successfully.");
    } catch (error) {
      console.error(error);
      setConfirmAction(null);
      setSettingsNotice("Failed to purge stored tracks.");
    }
  }

  async function handleScanLibrary() {
    if (isScanningLibrary) return

    setIsScanningLibrary(true)
    setConfirmAction(null)
    setSettingsNotice("Scanning Library...")
    try {
      const response = await fetch(`${API_BASE_URL}/api/scan?limit=100000`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to scan library");
      }

      const scanResult = await response.json();

      const [tracksResponse, artistsResponse, albumsResponse, playlistsResponse] =
        await Promise.all([
          fetch(`${API_BASE_URL}/api/tracks`),
          fetch(`${API_BASE_URL}/api/artists`),
          fetch(`${API_BASE_URL}/api/albums`),
          fetch(`${API_BASE_URL}/api/playlists`),
        ]);

      if (
        !tracksResponse.ok ||
        !artistsResponse.ok ||
        !albumsResponse.ok ||
        !playlistsResponse.ok
      ) {
        throw new Error("Failed to refresh library after scan");
      }

      const tracksData = await tracksResponse.json();
      const artistsData = await artistsResponse.json();
      const albumsData = await albumsResponse.json();
      const playlistsData = await playlistsResponse.json();

      setTracks(tracksData);
      setArtists(artistsData);
      setAlbums(albumsData);
      setPlaylists(
        [...playlistsData].sort((a, b) => {
          if (a.system_key === "liked_songs") return -1;
          if (b.system_key === "liked_songs") return 1;
          return a.name.localeCompare(b.name);
        })
      );

      setSettingsNotice(
        `Library scan completed. Added ${scanResult.added} new tracks${scanResult.added === 1 ? "" : "s"}.`
      )

    } catch (error) {
      console.error(error);
      setSettingsNotice("Failed to scan the music library.");
    } finally {
      setIsScanningLibrary(false)
    }
  }

  function handleSettingsToggle(key) {
    setAppSettings((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  }

  function handleSettingsTimeChange(key, value) {
    setAppSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  }

  async function handleSaveAppSettings() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/settings`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          cleanup_enabled: appSettings.cleanup_enabled,
          cleanup_time: appSettings.cleanup_time || null,
          scan_enabled: appSettings.scan_enabled,
          scan_time: appSettings.scan_time || null,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to save settings");
      }

      const savedSettings = await response.json();

      setAppSettings({
        cleanup_enabled: savedSettings.cleanup_enabled,
        cleanup_time: savedSettings.cleanup_time || "",
        scan_enabled: savedSettings.scan_enabled,
        scan_time: savedSettings.scan_time || "",
      });

      setSettingsNotice("Settings saved successfully.");
    } catch (error) {
      console.error(error);
      setSettingsNotice("Failed to save settings.");
    }
  }

  async function handleRunCleanupNow() {
    console.log("clicked")
    try {
      console.log("about to call cleanup api")
      const cleanupResponse = await fetch(
        `${API_BASE_URL}/api/maintenance/cleanup`,
        {
          method: "POST",
        }
      );

      if (!cleanupResponse.ok) {
        throw new Error("Failed to run cleanup");
      }

      const cleanupResult = await cleanupResponse.json();

      const [tracksResponse, artistsResponse, albumsResponse, playlistsResponse] =
        await Promise.all([
          fetch(`${API_BASE_URL}/api/tracks`),
          fetch(`${API_BASE_URL}/api/artists`),
          fetch(`${API_BASE_URL}/api/albums`),
          fetch(`${API_BASE_URL}/api/playlists`),
        ]);

      if (
        !tracksResponse.ok ||
        !artistsResponse.ok ||
        !albumsResponse.ok ||
        !playlistsResponse.ok
      ) {
        throw new Error("Failed to refresh library after cleanup");
      }

      const tracksData = await tracksResponse.json();
      const artistsData = await artistsResponse.json();
      const albumsData = await albumsResponse.json();
      const playlistsData = await playlistsResponse.json();

      setTracks(tracksData);
      setArtists(artistsData);
      setAlbums(albumsData);
      setPlaylists(
        [...playlistsData].sort((a, b) => {
          if (a.system_key === "liked_songs") return -1;
          if (b.system_key === "liked_songs") return 1;
          return a.name.localeCompare(b.name);
        })
      );

      setSettingsNotice(
        `Cleanup completed. Removed ${cleanupResult.removed} missing track${
          cleanupResult.removed === 1 ? "" : "s"
        }.`
      );
    } catch (error) {
      console.error(error);
      setSettingsNotice("Failed to run cleanup.");
    }
  }

  async function handleToggleLikedTrack() {
    if (!selectedTrack) {
      return;
    }

    try {
      const response = await fetch(
        isCurrentTrackLiked
          ? `${API_BASE_URL}/api/playlists/liked-songs/tracks/${selectedTrack.id}`
          : `${API_BASE_URL}/api/playlists/liked-songs/tracks`,
        isCurrentTrackLiked
          ? {
              method: "DELETE",
            }
          : {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ track_id: selectedTrack.id }),
            }
      );

      if (!response.ok) {
        throw new Error("Failed to toggle liked track");
      }

      const data = await response.json();
      setIsCurrentTrackLiked(data.liked);

      if (selectedPlaylist?.system_key === "liked_songs") {
        const likedSongsResponse = await fetch(
          `${API_BASE_URL}/api/playlists/${selectedPlaylist.id}/tracks`
        );

        if (likedSongsResponse.ok) {
          const likedSongsTracks = await likedSongsResponse.json();
          setPlaylistTracks(likedSongsTracks);
        }
      }
    } catch (error) {
      console.error(error);
    }
  }

  function handleOpenEditTrack(track) {
    setEditingTrack(track);
    setEditTrackTitle(track.title || "");
    setEditTrackArtist(track.artist || "");
    setEditTrackAlbum(track.album || "");
    setOpenMenuTrackId(null);
    setIsArtistMenuOpen(false);
    setIsCreatingArtist(false);
    setNewArtistName("");
    setIsAlbumMenuOpen(false);
    setIsCreatingAlbum(false);
    setNewAlbumName("");
  }

  function handleCloseEditTrack() {
    setEditingTrack(null);
    setEditTrackTitle("");
    setEditTrackArtist("");
    setEditTrackAlbum("");
    setIsArtistMenuOpen(false);
    setIsCreatingArtist(false);
    setNewArtistName("");
    setIsAlbumMenuOpen(false);
    setIsCreatingAlbum(false);
    setNewAlbumName("");
  }

  async function handleSaveTrackInfo() {
    if (!editingTrack) {
      return;
    }

    const trimmedTitle = editTrackTitle.trim();
    const trimmedArtist = editTrackArtist.trim();
    const trimmedAlbum = editTrackAlbum.trim();

    if (!trimmedTitle) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/tracks/${editingTrack.id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title: trimmedTitle,
            artist: trimmedArtist || null,
            album: trimmedAlbum || null,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to update track info");
      }

      const updatedTrack = await response.json();

      setTracks((prev) =>
        prev.map((track) =>
          track.id === updatedTrack.id ? updatedTrack : track
        )
      );

      setSelectedTrack((prev) =>
        prev?.id === updatedTrack.id ? updatedTrack : prev
      );

      setPlaylistTracks((prev) =>
        prev.map((track) =>
          track.id === updatedTrack.id ? updatedTrack : track
        )
      );

      setQueue((prev) =>
        prev.map((track) =>
          track.id === updatedTrack.id ? updatedTrack : track
        )
      );

      setOriginalQueue((prev) =>
        prev.map((track) =>
          track.id === updatedTrack.id ? updatedTrack : track
        )
      );

      const refreshedArtists = Array.from(
        new Set(
          tracks
            .map((track) =>
              track.id === updatedTrack.id ? updatedTrack.artist : track.artist
            )
            .filter(Boolean)
        )
      ).sort((a, b) => a.localeCompare(b));

      const refreshedAlbums = Array.from(
        new Set(
          tracks
            .map((track) =>
              track.id === updatedTrack.id ? updatedTrack.album : track.album
            )
            .filter(Boolean)
        )
      ).sort((a, b) => a.localeCompare(b));

      setArtists(refreshedArtists);
      setAlbums(refreshedAlbums);

      handleCloseEditTrack();
    } catch (error) {
      console.error(error);
    }
  }

  function handleOpenEditArtist() {
    if (!selectedArtist) {
      return;
    }

    setEditingArtistName(selectedArtist);
    setTransferArtistTarget("");
    setIsArtistActionsOpen(false);
    setIsEditArtistModalOpen(true);
    setIsTransferArtistMenuOpen(false);
  }

  function handleCloseEditArtist() {
    setEditingArtistName("");
    setTransferArtistTarget("");
    setIsArtistActionsOpen(false);
    setIsEditArtistModalOpen(false);
    setIsTransferArtistMenuOpen(false);
  }

  async function handleSaveArtistEdit() {
    if (!selectedArtist) {
      return;
    }

    const trimmedRename = editingArtistName.trim();
    const trimmedTransferTarget = transferArtistTarget.trim();

    let currentSourceArtist = selectedArtist;

    try {
      if (trimmedRename && trimmedRename !== selectedArtist) {
        const renameResponse = await fetch(
          `${API_BASE_URL}/api/artists/rename`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              current_artist: selectedArtist,
              new_artist: trimmedRename,
            }),
          }
        );

        if (!renameResponse.ok) {
          throw new Error("Failed to rename artist");
        }

        currentSourceArtist = trimmedRename;
      }

      if (trimmedTransferTarget) {
        const transferResponse = await fetch(
          `${API_BASE_URL}/api/artists/transfer`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              source_artist: currentSourceArtist,
              target_artist: trimmedTransferTarget,
            }),
          }
        );

        if (!transferResponse.ok) {
          throw new Error("Failed to transfer artist");
        }

        currentSourceArtist = trimmedTransferTarget;
      }

      const [
        tracksResponse,
        artistsResponse,
        albumsResponse,
        playlistsResponse,
      ] = await Promise.all([
        fetch(`${API_BASE_URL}/api/tracks`),
        fetch(`${API_BASE_URL}/api/artists`),
        fetch(`${API_BASE_URL}/api/albums`),
        fetch(`${API_BASE_URL}/api/playlists`),
      ]);

      if (
        !tracksResponse.ok ||
        !artistsResponse.ok ||
        !albumsResponse.ok ||
        !playlistsResponse.ok
      ) {
        throw new Error("Failed to refresh library after artist update");
      }

      const tracksData = await tracksResponse.json();
      const artistsData = await artistsResponse.json();
      const albumsData = await albumsResponse.json();
      const playlistsData = await playlistsResponse.json();

      setTracks(tracksData);
      setArtists(artistsData);
      setAlbums(albumsData);
      setPlaylists(
        [...playlistsData].sort((a, b) => {
          if (a.system_key === "liked_songs") return -1;
          if (b.system_key === "liked_songs") return 1;
          return a.name.localeCompare(b.name);
        })
      );

      setSelectedArtist(currentSourceArtist);
      handleCloseEditArtist();
    } catch (error) {
      console.error(error);
    }
  }

  const visibleTracks = useMemo(() => {
    return tracks.filter((track) => {
      const matchesArtist = selectedArtist ? track.artist === selectedArtist : true;
      const matchesAlbum = selectedAlbum ? track.album === selectedAlbum : true;

      const query = searchQuery.trim().toLowerCase();
      const matchesSearch =
        query === "" ||
        track.title?.toLowerCase().includes(query) ||
        track.artist?.toLowerCase().includes(query) ||
        track.album?.toLowerCase().includes(query);

      return matchesArtist && matchesAlbum && matchesSearch;
    });
  }, [tracks, selectedArtist, selectedAlbum, searchQuery]);

  const visibleArtists = useMemo(() => {
    return artists.filter((artist) =>
      artist.toLowerCase().includes(searchQuery.trim().toLowerCase())
    );
  }, [artists, searchQuery]);

  const visibleAlbums = useMemo(() => {
    return albums.filter((album) =>
      album.toLowerCase().includes(searchQuery.trim().toLowerCase())
    );
  }, [albums, searchQuery]);

  const paginatedTracks = visibleTracks.slice(
    (tracksPage - 1) * TRACKS_PAGE_SIZE,
    tracksPage * TRACKS_PAGE_SIZE
  );

  const totalTrackPages = Math.max(
    1,
    Math.ceil(visibleTracks.length / TRACKS_PAGE_SIZE)
  );

  const paginatedArtists = visibleArtists.slice(
    (artistsPage - 1) * ARTISTS_PAGE_SIZE,
    artistsPage * ARTISTS_PAGE_SIZE
  );

  const totalArtistPages = Math.max(
    1,
    Math.ceil(visibleArtists.length / ARTISTS_PAGE_SIZE)
  );

  const editArtistAlbums = useMemo(() => {
    return albums.filter((album) =>
      tracks.some(
        (track) =>
          (track.artist || "") === editTrackArtist &&
          (track.album || "") === album
      )
    );
  }, [albums, tracks, editTrackArtist]);

  function renderMainContent() {
    if (loading) {
      return <div className="state-message">Loading tracks...</div>
    }
    if (error) {
      return <div className="state-message">{error}</div>
    }
    if (activeView === "playlist") {
      if (playlistTracks.length === 0) {
        return <div className="state-message">This Playlist is empty.</div>
      }
      return (
        <div className="track-list">
          {playlistTracks.map((track, index) => (
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

              <div className="track-row__actions">
                <button
                  className="track-row__menu-button"
                  type="button"
                  aria-label="Track actions"
                  onClick={(event) => {
                    event.stopPropagation()
                    setOpenMenuTrackId((prev) => (prev === track.id ? null : track.id))
                  }}
                >
                  ⋯
                </button>

                {openMenuTrackId === track.id && (
                  <div
                    className="track-row__menu"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <button
                      className="track-row__menu-item"
                      onClick={() => handleOpenEditTrack(track)}
                      type="button"
                    >
                      Edit Info
                    </button>
                    <button
                      className="track-row__menu-item"
                      onClick={() => {
                        handleAddToQueue(track)
                        setOpenMenuTrackId(null)
                      }}
                      type="button"
                    >
                      Add to Queue
                    </button>
                    {playlists.length > 0 && (
                      <>
                        <div className="track-row__menu-divider" />
                        <div className="track-row__menu-label">Add to Playlist</div>

                        {playlists.map((playlist) => (
                          <button
                            key={playlist.id}
                            className="track-row__menu-item"
                            onClick={() => handleAddTrackToPlaylist(track.id, playlist.id)}
                            type="button"
                          >
                            {playlist.name}
                          </button>
                        ))}
                      </>
                    )}
                    <div className="track-row__menu-divider" />
                    <button
                      className="track-row__menu-item"
                      onClick={() => handleRemoveTrackFromPlaylist(track.id)}
                      type="button"
                    >
                      Remove from Playlist
                    </button>
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      )
    }
    if (activeView === "settings") {
      return (
        <div className="settings-page">
          {settingsNotice && (
            <div className="settings-notice">
              {settingsNotice}
            </div>
          )}
          <div className="settings-card settings-card--danger">
            <div className="settings-card__title">Purge stored tracks</div>
            <div className="settings-card__text">
              Warning: Removes all indexed tracks from the database and clears playlist track entries plus playback state. Music files on the volume, will not be deleted.
            </div>
            {confirmAction === "purge_tracks" ? (
              <div className="settings-card__actions">
                <button
                  className="settings-button settings-button--secondary"
                  type="button"
                  onClick={() => setConfirmAction(null)}
                >
                  Cancel
                </button>
                <button
                  className="settings-button settings-button--danger"
                  type="button"
                  onClick={handlePurgeTracks}
                >
                  Go Ahead
                </button>
              </div>
            ) : (
              <div className="settings-card__actions">
                <button
                  className="settings-button settings-button--danger"
                  type="button"
                  onClick={() => setConfirmAction("purge_tracks")}
                >
                  Purge Database Tracks
                </button>
              </div>
            )}
          </div>
          <div className="settings-card">
            <div className="settings-card__title">Scan entire music library</div>
            <div className="settings-card__text">
              Scans your full music library for new files and adds any newly found tracks
              to the database.
            </div>

            {confirmAction === "scan_library" ? (
              <div className="settings-card__actions">
                <button
                  className="settings-button settings-button--secondary"
                  type="button"
                  onClick={() => setConfirmAction(null)}
                >
                  Cancel
                </button>
            
                <button
                  className="settings-button"
                  type="button"
                  onClick={handleScanLibrary}
                  disabled={isScanningLibrary}
                >
                  {isScanningLibrary ? "Scanning..." : "Go ahead"}
                </button>
              </div>
            ) : (
              <div className="settings-card__actions">
                <button
                  className="settings-button"
                  type="button"
                  onClick={() => setConfirmAction("scan_library")}
                  disabled={isScanningLibrary}
                >
                  {isScanningLibrary ? "Scanning..." : "Scan library now"}
                </button>
              </div>
            )}
          </div>
          <div className="settings-card">
            <div className="settings-card__title">Run cleanup now</div>
            <div className="settings-card__text">
              Immediately remove tracks from the database if their music files no longer
              exist on disk.
            </div>

            <div className="settings-card__actions">
              <button
                className="settings-button"
                type="button"
                onClick={handleRunCleanupNow}
              >
                Run cleanup now
              </button>
            </div>
          </div>
          <div className="settings-card">
            <div className="settings-card__title">Cleanup missing files</div>
            <div className="settings-card__text">
              Check whether indexed music files still exist on disk and remove missing
              files from the database and track lists.
            </div>

            <label className="settings-field settings-field--inline">
              <input
                type="checkbox"
                checked={appSettings.cleanup_enabled}
                onChange={() => handleSettingsToggle("cleanup_enabled")}
              />
              <span>Enable daily cleanup</span>
            </label>

            <label className="settings-field">
              <span className="settings-field__label">Run time</span>
              <input
                className="settings-time-input"
                type="time"
                value={appSettings.cleanup_time}
                onChange={(event) =>
                  handleSettingsTimeChange("cleanup_time", event.target.value)
                }
              />
            </label>
          </div>
              
          <div className="settings-card">
            <div className="settings-card__title">Scan library for new files</div>
            <div className="settings-card__text">
              Scan the music library on a schedule and add newly discovered tracks to the
              database.
            </div>
              
            <label className="settings-field settings-field--inline">
              <input
                type="checkbox"
                checked={appSettings.scan_enabled}
                onChange={() => handleSettingsToggle("scan_enabled")}
              />
              <span>Enable daily scan</span>
            </label>
              
            <label className="settings-field">
              <span className="settings-field__label">Run time</span>
              <input
                className="settings-time-input"
                type="time"
                value={appSettings.scan_time}
                onChange={(event) =>
                  handleSettingsTimeChange("scan_time", event.target.value)
                }
              />
            </label>
          </div>
              
          <div className="settings-card__actions">
            <button
              className="settings-button"
              type="button"
              onClick={handleSaveAppSettings}
            >
              Save schedule settings
            </button>
          </div>
        </div>
      );
    }
    if (activeView === "artists") {
      return (
        <div className="simple-list">
          {paginatedArtists.map((artist) => (
            <button
              key={artist}
              className="simple-list__row simple-list__row--button"
              onClick={() => handleArtistClick(artist)}
              type="button"
            >
              {artist}
            </button>
          ))}

          {totalArtistPages > 1 && (
              <div className="pagination">
                <button
                  className="pagination__button"
                  type="button"
                  onClick={() => setArtistsPage((prev) => Math.max(1, prev - 1))}
                  disabled={artistsPage === 1}
                >
                  Previous
                </button>
          
                <span className="pagination__label">
                  Page {artistsPage} of {totalArtistPages}
                </span>
          
                <button
                  className="pagination__button"
                  type="button"
                  onClick={() =>
                    setArtistsPage((prev) => Math.min(totalArtistPages, prev + 1))
                  }
                  disabled={artistsPage === totalArtistPages}
                >
                  Next
                </button>
              </div>
            )}
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
        {paginatedTracks.map((track, index) => (
          <button
            key={track.id}
            className={`track-row ${
              selectedTrack?.id === track.id ? "track-row--active" : ""
            }`}
            onClick={() => handleTrackClick(track)}
            type="button"
          >
            <div className="track-row__index">
              {(tracksPage - 1) * TRACKS_PAGE_SIZE + index + 1}
            </div>
            
            <div className="track-row__content">
              <div className="track-row__title">{track.title}</div>
              <div className="track-row__meta">
                {track.artist || "Unknown Artist"} •{" "}
                {track.album || "Unknown Album"}
              </div>
            </div>
            <div className="track-row__actions">
              <button
                className="track-row__menu-button"
                type="button"
                aria-label="Track actions"
                onClick={(event) => {
                  event.stopPropagation()
                  setOpenMenuTrackId((prev) =>
                    prev === track.id ? null : track.id
                  )
                }}
              >
                ⋯
              </button>
            {openMenuTrackId === track.id && (
              <div
                className="track-row__menu"
                onClick={(event) => event.stopPropagation()}
              >
                <button
                  className="track-row__menu-item"
                  onClick={() => handleOpenEditTrack(track)}
                  type="button"
                >
                  Edit Info
                </button>
                <button
                  className="track-row__menu-item"
                  onClick={() => {
                    handleAddToQueue(track);
                    setOpenMenuTrackId(null);
                  }}
                  type="button"
                >
                  Add to Queue
                </button>

                {playlists.length > 0 && (
                  <>
                    <div className="track-row__menu-divider" />
                    <div className="track-row__menu-label">Add to Playlist</div>

                    {playlists.map((playlist) => (
                      <button
                        key={playlist.id}
                        className="track-row__menu-item"
                        onClick={() => handleAddTrackToPlaylist(track.id, playlist.id)}
                        type="button"
                      >
                        {playlist.name}
                      </button>
                    ))}
                  </>
                )}
              </div>
            )}
            </div>
          </button>
        ))}

        {totalTrackPages > 1 && (
          <div className="pagination">
            <button
              className="pagination__button"
              type="button"
              onClick={() => setTracksPage((prev) => Math.max(1, prev - 1))}
              disabled={tracksPage === 1}
            >
              Previous
            </button>
        
            <span className="pagination__label">
              Page {tracksPage} of {totalTrackPages}
            </span>
        
            <button
              className="pagination__button"
              type="button"
              onClick={() =>
                setTracksPage((prev) => Math.min(totalTrackPages, prev + 1))
              }
              disabled={tracksPage === totalTrackPages}
            >
              Next
            </button>
          </div>
        )}

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
    if (activeView === "playlist" && selectedPlaylist) {
      return selectedPlaylist.name
    }
    if (activeView === "settings") {
      return "Settings";
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
    if (activeView === "playlist" && selectedPlaylist) {
      return `${playlistTracks.length} tracks`
    }
    if (activeView === "settings") {
      return "App preferences and playback options";
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
        <div className="sidebar__header">
          <img className="logo" src="/Adjacent.svg" alt="Adjacent logo" />
          <div className="sidebar__brand">Adjacent</div>
        </div>

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

        <div className="sidebar__section sidebar__section--playlists">
          <div className="sidebar__section-header">
            <div className="sidebar__section-title">Playlists</div>
            <button
              className="sidebar__section-action"
              type="button"
              aria-label="Create playlist"
              onClick={() => setIsCreatingPlaylist((prev) => !prev)}
            >
              +
            </button>
          </div>
          {isCreatingPlaylist && (
            <div className="playlist-create">
              <input
                className="playlist-create__input"
                type="text"
                placeholder="New Playlist"
                value={newPlaylistName}
                onChange={(event) => setNewPlaylistName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    handleCreatePlaylist()
                  }
                  if (event.key === "Escape") {
                    setIsCreatingPlaylist(false)
                    setNewPlaylistName("")
                  }
                }}
                autoFocus
              />
              <button
                className="playlist-create__button"
                type="button"
                onClick={handleCreatePlaylist}
              >
                Create
              </button>
            </div>
          )}
          {playlists.length === 0 ? (
            <div className="sidebar__stat">No playlists yet</div>
          ) : (
            playlists.map((playlist) => (
              <div key={playlist.id} className="playlist-sidebar-item">
                {editingPlaylistId === playlist.id ? (
                    <input
                      className="playlist-sidebar-item__input"
                      type="text"
                      value={editingPlaylistName}
                      autoFocus
                      onChange={(event) => setEditingPlaylistName(event.target.value)}
                      onClick={(event) => event.stopPropagation()}
                      onBlur={handleCancelRenamePlaylist}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          handleSubmitRenamePlaylist(playlist.id);
                        }
                      
                        if (event.key === "Escape") {
                          handleCancelRenamePlaylist();
                        }
                      }}
                    />
                  ) : (
                    <button
                      className={`sidebar__link playlist-sidebar-item__main ${
                        activeView === "playlist" && selectedPlaylist?.id === playlist.id
                          ? "sidebar__link--active"
                          : ""
                      }`}
                      onClick={() => handlePlaylistClick(playlist)}
                      type="button"
                    >
                      {playlist.name}
                    </button>
                  )}
                  {!playlist.is_system && (
                    <div className="playlist-sidebar-item__actions">
                      <button
                        className="playlist-sidebar-item__menu-button"
                        type="button"
                        aria-label="Playlist actions"
                        onClick={(event) => {
                          event.stopPropagation()
                          setOpenPlaylistMenuId((prev) =>
                            prev === playlist.id ? null : playlist.id
                          )
                        }}
                      >
                        ⋯
                      </button>

                      {openPlaylistMenuId === playlist.id && (
                        <div
                          className="playlist-sidebar-item__menu"
                          onClick={(event) => event.stopPropagation()}
                        >
                          <button
                            className="playlist-sidebar-item__menu-item"
                            type="button"
                            onClick={() => handleStartRenamePlaylist(playlist)}
                          >
                            Rename Playlist
                          </button>

                          <button
                            className="playlist-sidebar-item__menu-item"
                            type="button"
                            onClick={() => handleDeletePlaylist(playlist.id)}
                          >
                            Delete Playlist
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
          <div className="sidebar__section">
            <button
              className={`sidebar__link ${activeView === "settings" ? "sidebar__link--active"             : ""}`}
              onClick={() => {
                setActiveView("settings");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedPlaylist(null);
              }}
              type="button"
            >
              Settings
            </button>
          </div>
        <div className="sidebar__section">
          <div className="sidebar__section-title">Library</div>
          <div className="sidebar__stat">Tracks: {tracks.length}</div>
          <div className="sidebar__stat">Artists: {artists.length}</div>
          <div className="sidebar__stat">Albums: {albums.length}</div>
        </div>
      </aside>

      <main className="main-content">
        <div className={`content-layout ${isQueueOpen ? "content-layout--queue-open" : ""}`}>
          <div className="content-layout__main">
            <header className="main-content__header">
              <div className="main-content__header-row">
                <div>
                  <h1>{getHeaderTitle()}</h1>
                  {!loading && !error && (
                    <p className="main-content__subhead">{getHeaderSubtitle()}</p>
                  )}
                </div>
                
                {activeView === "tracks" && selectedArtist && (
                  <div className="page-actions">
                    <button
                      className="page-actions__button"
                      type="button"
                      aria-label="Artist actions"
                      onClick={() => setIsArtistActionsOpen((prev) => !prev)}
                    >
                      ⋯
                    </button>
                
                    {isArtistActionsOpen && (
                      <div className="page-actions__menu">
                        <button
                          className="page-actions__menu-item"
                          type="button"
                          onClick={handleOpenEditArtist}
                        >
                          Edit Artist
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </header>
            {activeView !== "settings" && (
              <div className="search-bar">
                <input
                  className="search-input"
                  placeholder={`Search ${activeView}...`}
                  type="text"
                  value={searchQuery}
                  onChange={(event)=> setSearchQuery(event.target.value)}
                />
              </div>
            )}
            <section className="main-content__body">{renderMainContent()}</section>
          </div>
          {isQueueOpen && (
            <aside className="queue-panel">
              <div className="queue-panel__header">
                <h2>Queue</h2>
                <p>{queue.length} tracks</p>
              </div>
          
              {queueIndex >= 0 && queue[queueIndex] && (
                <div className="queue-panel__section">
                  <div className="queue-panel__section-title">Now Playing</div>
              
                  <button
                    className="queue-panel__item queue-panel__item--active"
                    onClick={() => {
                      setSelectedTrack(queue[queueIndex]);
                      setQueueIndex(queueIndex);
                    }}
                    type="button"
                  >
                    <div className="queue-panel__item-title">{queue[queueIndex].title}</div>
                    <div className="queue-panel__item-meta">
                      {queue[queueIndex].artist || "Unknown Artist"}
                    </div>
                  </button>
                </div>
              )}

              <div className="queue-panel__section">
                <div className="queue-panel__section-title">Next Up</div>
            
                <div className="queue-panel__list">
                  {queue
                    .slice(queueIndex + 1)
                    .map((track, index) => {
                      const actualIndex = queueIndex + 1 + index;
                    
                      return (
                        <div
                          key={`${track.id}-${actualIndex}`}
                          className="queue-panel__item queue-panel__item--row"
                        >
                          <button
                            className="queue-panel__item-main"
                            onClick={() => {
                              setSelectedTrack(track);
                              setQueueIndex(actualIndex);
                            }}
                            type="button"
                          >
                            <div className="queue-panel__item-title">{track.title}</div>
                            <div className="queue-panel__item-meta">
                              {track.artist || "Unknown Artist"}
                            </div>
                          </button>
                          
                          <button
                            className="queue-panel__remove-button"
                            onClick={() => handleRemoveFromQueue(actualIndex)}
                            type="button"
                            aria-label="Remove from queue"
                          >
                            ×
                          </button>
                        </div>
                      );
                    })}
                </div>
              </div>
            </aside>
          )}
        </div>
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
          <button
            className={`player-bar__icon-button player-bar__like-button ${
              isCurrentTrackLiked ? "player-bar__icon-button--active" : ""
            }`}
            type="button"
            aria-label={isCurrentTrackLiked ? "Remove from liked songs" : "Add to likedsongs"}
            onClick={handleToggleLikedTrack}
            disabled={!selectedTrack}
          >
            {isCurrentTrackLiked ? "♥" : "♡"}
          </button>
            <button 
              className={`player-bar__icon-button ${
                isShuffle ? "player-bar__icon-button--active" : ""
              }`}
              type="button" 
              aria-label="Shuffle"
              onClick={handleToggleShuffle}
            >
              ⇄
            </button>

            <button 
              className="player-bar__icon-button" 
              type="button" 
              aria-label="Previous track"
              onClick={handlePreviousTrack}
            >
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

            <button 
              className="player-bar__icon-button" 
              type="button" 
              aria-label="Next track"
              onClick={handleNextTrack}
            >
              ⏭
            </button>

            <button 
              className={`player-bar__icon-button ${
                isLoop ? "player-bar__icon-button--active" : ""
              }`}
              type="button" 
              aria-label="Loop"
              onClick={handleToggleLoop}
            >
              ↺
            </button>
          </div>

          <div className="player-bar__progress-row">
            <span className="player-bar__time">{formatTime(currentTime)}</span>
            <div 
              className="player-bar__progress-track"
              onClick={handleSeek}
              ref={progressBarRef}
              role="button"
              tabIndex={0}
            >
            <div 
              className="player-bar__progress-fill" 
              style={{ width: `${progressPercent}%`}}
            />
          </div>
            <span className="player-bar__time">{formatTime(duration)}</span>
          </div>
        </div>
        <div className="player-bar__right">
          <button
            className={`player-bar__icon-button ${
              isQueueOpen ? "player-bar__icon-button--active" : ""
            }`}
            type="button"
            aria-label="Queue"
            onClick={handleToggleQueue}
          >
            ☰
          </button>
          <button
            className="player-bar__icon-button"
            type="button"
            aria-label={isMuted ? "Unmute" : "Mute"}
            onClick={handleToggleMute}
          >
            {isMuted || volume === 0 ? "🔇" : "🔊"}
          </button>
          <input
            className="player-bar__volume-slider"
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={isMuted ? 0 : volume}
            onChange={handleVolumeChange}
            aria-label="Volume"
          />
        </div>

        <audio
          ref={audioRef}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => {
            setCurrentTime(0);
            if (isLoop && audioRef.current) {
              audioRef.current.currentTime = 0
              audioRef.current.play()
              setIsPlaying(true)
              return
            }
            playNextAvailableTrack();

          }}
          onTimeUpdate={() =>{
            if (audioRef.current) {
              setCurrentTime(audioRef.current.currentTime)
            }
          }}
          onLoadedMetadata={() => {
            if (audioRef.current) {
              setDuration(audioRef.current.duration)
              if(Number.isFinite(pendingSeekRef.current)) {
                audioRef.current.currentTime = pendingSeekRef.current
                pendingSeekRef.current = null
              }
            }
          }}
        />
      </footer>
      {editingTrack && (
        <div className="modal-overlay" onClick={handleCloseEditTrack}>
          <div
            className="modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal__header">
              <h2>Edit Info</h2>
            </div>

            <div className="modal__body">
              <label className="modal__field">
                <span className="modal__label">Artist</span>

                <div className="modal__select-row">
                  <button
                    className="modal__select"
                    type="button"
                    onClick={() => {
                      setIsArtistMenuOpen((prev) => !prev);
                      setIsCreatingArtist(false);
                      setNewArtistName("");
                    }}
                  >
                    {editTrackArtist || "Select artist"}
                  </button>
                  
                  <button
                    className="modal__plus-button"
                    type="button"
                    onClick={() => {
                      setIsCreatingArtist((prev) => !prev);
                      setIsArtistMenuOpen(false);
                      setNewArtistName("");
                    }}
                  >
                    +
                  </button>
                </div>
                  
                {isArtistMenuOpen && (
                  <div className="modal__dropdown">
                    {artists.map((artist) => (
                      <button
                        key={artist}
                        className="modal__dropdown-item"
                        type="button"
                        onClick={() => {
                          setEditTrackArtist(artist);
                          setIsArtistMenuOpen(false);
                        }}
                      >
                        {artist}
                      </button>
                    ))}
                  </div>
                )}

                {isCreatingArtist && (
                  <div className="modal__inline-create">
                    <input
                      className="modal__input"
                      type="text"
                      placeholder="New artist name"
                      value={newArtistName}
                      onChange={(event) => setNewArtistName(event.target.value)}
                    />

                    <div className="modal__inline-actions">
                      <button
                        className="settings-button settings-button--secondary"
                        type="button"
                        onClick={() => {
                          setIsCreatingArtist(false);
                          setNewArtistName("");
                        }}
                      >
                        Cancel
                      </button>
                      
                      <button
                        className="settings-button"
                        type="button"
                        onClick={() => {
                          const trimmed = newArtistName.trim();
                          if (!trimmed) return;
                        
                          setEditTrackArtist(trimmed);
                          setIsCreatingArtist(false);
                          setNewArtistName("");
                        }}
                      >
                        Use artist
                      </button>
                    </div>
                  </div>
                )}
              </label>
              <label className="modal__field">
                <span className="modal__label">Album</span>

                <div className="modal__select-row">
                  <button
                    className="modal__select"
                    type="button"
                    onClick={() => {
                      setIsAlbumMenuOpen((prev) => !prev);
                      setIsCreatingAlbum(false);
                      setNewAlbumName("");
                    }}
                  >
                    {editTrackAlbum || "Select album"}
                  </button>
                  
                  <button
                    className="modal__plus-button"
                    type="button"
                    onClick={() => {
                      setIsCreatingAlbum((prev) => !prev);
                      setIsAlbumMenuOpen(false);
                      setNewAlbumName("");
                    }}
                  >
                    +
                  </button>
                </div>
                  
                {isAlbumMenuOpen && (
                  <div className="modal__dropdown">
                    {editArtistAlbums.map((album) => (
                      <button
                        key={album}
                        className="modal__dropdown-item"
                        type="button"
                        onClick={() => {
                          setEditTrackAlbum(album);
                          setIsAlbumMenuOpen(false);
                        }}
                      >
                        {album}
                      </button>
                    ))}

                    {editArtistAlbums.length === 0 && (
                      <div className="modal__dropdown-empty">
                        No albums found for this artist
                      </div>
                    )}
                  </div>
                )}

                {isCreatingAlbum && (
                  <div className="modal__inline-create">
                    <input
                      className="modal__input"
                      type="text"
                      placeholder="New album name"
                      value={newAlbumName}
                      onChange={(event) => setNewAlbumName(event.target.value)}
                    />

                    <div className="modal__inline-actions">
                      <button
                        className="settings-button settings-button--secondary"
                        type="button"
                        onClick={() => {
                          setIsCreatingAlbum(false);
                          setNewAlbumName("");
                        }}
                      >
                        Cancel
                      </button>
                      
                      <button
                        className="settings-button"
                        type="button"
                        onClick={() => {
                          const trimmed = newAlbumName.trim();
                          if (!trimmed) return;
                        
                          setEditTrackAlbum(trimmed);
                          setIsCreatingAlbum(false);
                          setNewAlbumName("");
                        }}
                      >
                        Use album
                      </button>
                    </div>
                  </div>
                )}
              </label>
              <label className="modal__field">
                <span className="modal__label">Track name</span>
                <input
                  className="modal__input"
                  type="text"
                  value={editTrackTitle}
                  onChange={(event) => setEditTrackTitle(event.target.value)}
                />
              </label>
            </div>
            <div className="modal__actions">
              <button
                className="settings-button settings-button--secondary"
                type="button"
                onClick={handleCloseEditTrack}
              >
                Cancel
              </button>

              <button
                className="settings-button"
                type="button"
                onClick={handleSaveTrackInfo}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
      {isEditArtistModalOpen && (
        <div className="modal-overlay" onClick={handleCloseEditArtist}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal__header">
              <h2>Edit Artist</h2>
            </div>
      
            <div className="modal__body">
              <label className="modal__field">
                <span className="modal__label">Rename artist</span>
                <input
                  className="modal__input"
                  type="text"
                  value={editingArtistName}
                  onChange={(event) => setEditingArtistName(event.target.value)}
                />
              </label>
              <label className="modal__field">
                <span className="modal__label">Transfer all songs and albums to</span>

                <div className="modal__select-row">
                  <button
                    className="modal__select"
                    type="button"
                    onClick={() => setIsTransferArtistMenuOpen((prev) => !prev)}
                  >
                    {transferArtistTarget || "Select another artist"}
                  </button>
                </div>

                {isTransferArtistMenuOpen && (
                  <div className="modal__dropdown">
                    {artists
                      .filter((artist) => artist !== selectedArtist)
                      .map((artist) => (
                        <button
                          key={artist}
                          className="modal__dropdown-item"
                          type="button"
                          onClick={() => {
                            setTransferArtistTarget(artist);
                            setIsTransferArtistMenuOpen(false);
                          }}
                        >
                          {artist}
                        </button>
                      ))}
                  </div>
                )}
              </label>
            </div>
            <div className="modal__actions">
              <button
                className="settings-button settings-button--secondary"
                type="button"
                onClick={handleCloseEditArtist}
              >
                Cancel
              </button>
                  
              <button
                className="settings-button"
                type="button"
                onClick={handleSaveArtistEdit}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;