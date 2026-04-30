import { useEffect, useMemo, useRef, useState } from "react";
import { List } from "react-window";

function App() {
  const [authLoading, setAuthLoading] = useState(true);
  const [setupRequired, setSetupRequired] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [authError, setAuthError] = useState("");
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
    lastfm_enrichment_enabled: false,
    lastfm_enrichment_time: "",
  });
  const [lastfmReadiness, setLastfmReadiness] = useState({
    total_tracks: 0,
    tracks_with_mbid: 0,
    tracks_missing_mbid: 0,
    progress_percent: 0,
    ready: false,
    musicbrainz_backfill_running: false,
    musicbrainz_resume_available: false,
  })
  const [tracksPage, setTracksPage] = useState(1);
  const [artistsPage, setArtistsPage] = useState(1);
  const [isScanningLibrary, setIsScanningLibrary] = useState(false);
  const [likedSongsPlaylist, setLikedSongsPlaylist] = useState(null);
  const [isCurrentTrackLiked, setIsCurrentTrackLiked] = useState(false);
  const [editingTrack, setEditingTrack] = useState(null);
  const [editTrackTitle, setEditTrackTitle] = useState("");
  const [editTrackArtist, setEditTrackArtist] = useState("");
  const [editTrackAlbum, setEditTrackAlbum] = useState("");
  const [editTrackGenres, setEditTrackGenres] = useState("");
  const [isArtistMenuOpen, setIsArtistMenuOpen] = useState(false);
  const [selectedArtistArtworkPath, setSelectedArtistArtworkPath] = useState("");
  const [artistArtworkMap, setArtistArtworkMap] = useState({});
  const [artistArtworkFile, setArtistArtworkFile] = useState(null);
  const [artistArtworkPreviewUrl, setArtistArtworkPreviewUrl] = useState("");
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
  const API_BASE_URL =
    window.APP_CONFIG?.API_BASE_URL ||
    `${window.location.protocol}//${window.location.hostname}:8000`;
  const [artworkPlaylist, setArtworkPlaylist] = useState(null);
  const [albumArtworkMap, setAlbumArtworkMap] = useState({});
  const [artworkAlbum, setArtworkAlbum] = useState(null);
  const [albumArtworkFile, setAlbumArtworkFile] = useState(null);
  const [albumArtworkPreviewUrl, setAlbumArtworkPreviewUrl] = useState("");
  const [artworkFile, setArtworkFile] = useState(null);
  const [artworkPreviewUrl, setArtworkPreviewUrl] = useState("");
  const [genres, setGenres] = useState([]);
  const [selectedGenre, setSelectedGenre] = useState(null);
  const [selectedArtistGenres, setSelectedArtistGenres] = useState([]);
  const [similarTracks, setSimilarTracks] = useState([]);
  const [similarRefreshKey, setSimilarRefreshKey] = useState(0);
  const [lastfmApiKey, setLastfmApiKey] = useState("");
  const [lastfmApiSecret, setLastfmApiSecret] = useState("")
  const [lastfmUsername, setLastfmUsername] = useState("")
  const [lastfmSessionKey, setLastfmSessionKey] = useState("")
  const [isLastfmConnecting, setIsLastfmConnecting] = useState(false)
  const [isLastfmEnriching, setIsLastfmEnriching] = useState(false);
  const [lastfmEnrichmentSummary, setLastfmEnrichmentSummary] = useState(null);
  const [lastfmProgress, setLastfmProgress] = useState(null)
  const [isResumingMusicbrainz, setIsResumingMusicbrainz] = useState(false)
  const [statsOverview, setStatsOverview] = useState({
    top_played: [],
    most_liked: [],
    most_skipped: [],
    recently_played: [],
  });
  const [isLoadingStatsOverview, setIsLoadingStatsOverview] = useState(false);
  const [artistViewMode, setArtistViewMode] = useState("list");

  const TRACKS_PAGE_SIZE = 50;
  const ARTISTS_PAGE_SIZE = 50;
  const SIMILAR_TRACK_LIMIT = 10;

  const audioRef = useRef(null);
  const progressBarRef = useRef(null)
  const pendingSeekRef = useRef(null)

  const playbackSessionIdRef = useRef(null);
  const playbackEventTrackIdRef = useRef(null);
  const hasSentPlayStartRef = useRef(false);
  const hasSentSkipRef = useRef(false);
  const hasSentCompleteRef = useRef(false);
  
  const lastfmProgressIntervalRef = useRef(null)

  const lastNowPlayingTrackIdRef = useRef(null)
  const lastScrobbledTrackIdRef = useRef(null)
  const listenedSecondsRef = useRef(0)
  const lastPlaybackTickRef = useRef(null)

  const musicbrainzReadinessIntervalRef = useRef(null)

  function createPlaybackSessionId() {
    return `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }

  function getListeningSource() {
    if (activeView === "playlist" && selectedPlaylist) {
      return {
        source_type: "playlist",
        source_id: selectedPlaylist.id,
      };
    }

    if (selectedAlbum) {
      return {
        source_type: "album",
        source_id: null,
      };
    }

    if (selectedArtist) {
      return {
        source_type: "artist",
        source_id: null,
      };
    }

    return {
      source_type: "library",
      source_id: null,
    };
  }

  async function postListeningEvent(trackId, eventPath, overrides = {}) {
    try {
      const source = getListeningSource();

      const response = await fetch(`${API_BASE_URL}/api/tracks/${trackId}/${eventPath}`, {
        credentials: "include",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source_type: source.source_type,
          source_id: source.source_id,
          position_seconds: audioRef.current?.currentTime ?? 0,
          duration_seconds: audioRef.current?.duration || duration || null,
          session_id: playbackSessionIdRef.current,
          ...overrides,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed listening event: ${eventPath}`);
      }

      const data = await response.json();
      fetchStatsOverview();
      return data;
    } catch (error) {
      console.error(error);
      return null;
    }
  }

  async function sendPlayStartEvent(track) {
    if (!track) return;
    if (hasSentPlayStartRef.current && playbackEventTrackIdRef.current === track.id) {
      return;
    }

    if (!playbackSessionIdRef.current || playbackEventTrackIdRef.current !== track.id) {
      playbackSessionIdRef.current = createPlaybackSessionId();
    }

    playbackEventTrackIdRef.current = track.id;
    hasSentPlayStartRef.current = true;
    hasSentSkipRef.current = false;
    hasSentCompleteRef.current = false;

    await postListeningEvent(track.id, "play-start", {
      position_seconds: audioRef.current?.currentTime ?? 0,
      duration_seconds: audioRef.current?.duration || duration || null,
    });
  }

  async function sendSkipEvent(track) {
    if (!track) return;
    if (hasSentSkipRef.current) {
      return;
    }

    hasSentSkipRef.current = true;

    await postListeningEvent(track.id, "skip", {
      position_seconds: audioRef.current?.currentTime ?? currentTime ?? 0,
      duration_seconds: audioRef.current?.duration || duration || null,
    });
  }

  async function sendPlayCompleteEvent(track) {
    if (!track) return;
    if (hasSentCompleteRef.current) {
      return;
    }

    hasSentCompleteRef.current = true;

    const finalDuration = audioRef.current?.duration || duration || null;

    await postListeningEvent(track.id, "play-complete", {
      position_seconds: finalDuration,
      duration_seconds: finalDuration,
    });
  }

  function resetPlaybackEventFlagsForTrack(track) {
    playbackEventTrackIdRef.current = track?.id ?? null;
    playbackSessionIdRef.current = track ? createPlaybackSessionId() : null;
    hasSentPlayStartRef.current = false;
    hasSentSkipRef.current = false;
    hasSentCompleteRef.current = false;
  }

  useEffect(() => {
    async function loadAuthState() {
      try {
        setAuthLoading(true);
        setAuthError("");

        const setupResponse = await fetch(`${API_BASE_URL}/api/auth/setup-status`, {
          credentials: "include",
        });

        if (!setupResponse.ok) {
          throw new Error("Unable to check setup status");
        }

        const setupData = await setupResponse.json();

        if (!setupData.admin_exists) {
          setSetupRequired(true);
          setCurrentUser(null);
          return;
        }

        setSetupRequired(false);

        const meResponse = await fetch(`${API_BASE_URL}/api/auth/me`, {
          credentials: "include",
        });

        if (meResponse.ok) {
          const user = await meResponse.json();
          setCurrentUser(user);
        } else {
          setCurrentUser(null);
        }
      } catch (error) {
        setAuthError(error.message || "Authentication failed");
        setCurrentUser(null);
      } finally {
        setAuthLoading(false);
      }
    }

    loadAuthState();
  }, []);

  useEffect(() =>{
    async function fetchLibraryData() {
      try {
        const [
          tracksResponse,
          artistsResponse,
          albumsResponse,          
          genresResponse,
          playlistsResponse,
          settingsResponse,
          lastfmReadinessResponse,
          likedSongsPlaylistResponse

        ] = await Promise.all([
          fetch(`${API_BASE_URL}/api/tracks`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/artists`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/albums`, { credentials: "include" }),          
          fetch(`${API_BASE_URL}/api/genres`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/playlists`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/settings`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/settings/lastfm/readiness`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/playlists/liked-songs`, { credentials: "include" })
        ])

        if (
          !tracksResponse.ok ||
          !artistsResponse.ok ||
          !albumsResponse.ok ||
          !genresResponse.ok ||
          !playlistsResponse.ok ||
          !settingsResponse.ok ||
          !lastfmReadinessResponse.ok ||
          !likedSongsPlaylistResponse.ok
        ) {
          throw new Error("Failed to fetch library data");
        }

        const tracksData = await tracksResponse.json();
        const artistsData = await artistsResponse.json();
        const albumsData = await albumsResponse.json();
        const playlistsData = await playlistsResponse.json();
        const settingsData = await settingsResponse.json()
        const lastfmReadinessData = await lastfmReadinessResponse.json();
        const likedSongsPlaylistData = await likedSongsPlaylistResponse.json();
        const genresData = await genresResponse.json();

        setTracks(tracksData);
        setArtists(artistsData);
        setAlbums(albumsData);
        setGenres(genresData);
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
          lastfm_enrichment_enabled: settingsData.lastfm_enrichment_enabled,
          lastfm_enrichment_time: settingsData.lastfm_enrichment_time || "",
        })
        setLastfmReadiness(lastfmReadinessData);
        setLikedSongsPlaylist(likedSongsPlaylistData);
        setLastfmApiKey(settingsData.lastfm_api_key || "");
        setLastfmApiSecret(settingsData.lastfm_api_secret || "")
        setLastfmUsername(settingsData.lastfm_username || "")
        setLastfmSessionKey(settingsData.lastfm_session_key || "")

        // Restore playback state
        const playbackResponse = await fetch(`${API_BASE_URL}/api/playback`, {
          credentials: "include"
        });

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
        await fetchStatsOverview();
      } catch (err) {
        setError("Could not load tracks.");
      } finally {
        setHasRestoredPlayback(true);
        setLoading(false);
      }
    }
  if (!authLoading && currentUser) {
    fetchLibraryData();
  }
  }, [authLoading, currentUser]);

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
    if (!selectedTrack) {
      lastNowPlayingTrackIdRef.current = null
      lastScrobbledTrackIdRef.current = null
      listenedSecondsRef.current = 0
      lastPlaybackTickRef.current = null
      resetPlaybackEventFlagsForTrack(null);
      return
    }

    lastNowPlayingTrackIdRef.current = null
    lastScrobbledTrackIdRef.current = null
    listenedSecondsRef.current = 0
    lastPlaybackTickRef.current = null
    resetPlaybackEventFlagsForTrack(selectedTrack);
  }, [selectedTrack?.id])

  useEffect(() => {
    async function handleLastfmCallback() {
      const currentUrl = new URL(window.location.href)
      const token = currentUrl.searchParams.get("token")

      if (!token) {
        return
      }

      if (!window.location.pathname.includes("/settings/lastfm/callback")) {
        return
      }

      setIsLastfmConnecting(true)

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/settings/lastfm/session?token=${encodeURIComponent(token)}`,
          {
            credentials: "include",
            method: "POST",
          }
        )

        if (!response.ok) {
          throw new Error("Failed to create Last.fm session")
        }

        const data = await response.json()

        setLastfmApiKey(data.lastfm_api_key || "")
        setLastfmApiSecret(data.lastfm_api_secret || "")
        setLastfmUsername(data.lastfm_username || "")
        setLastfmSessionKey(data.lastfm_session_key || "")
        setSettingsNotice("Last.fm connected successfully.")
        setActiveView("settings")

        window.history.replaceState({}, "", "/")
      } catch (error) {
        console.error(error)
        setSettingsNotice("Failed to complete Last.fm connection.")
      } finally {
        setIsLastfmConnecting(false)
      }
    }

    handleLastfmCallback()
  }, [])

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
          credentials: "include",
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
          credentials: "include",
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
    if (!selectedTrack) {
      return
    }

    if (!isPlaying) {
      lastPlaybackTickRef.current = null
      return
    }

    const intervalId = window.setInterval(() => {
      const now = Date.now()

      if (lastPlaybackTickRef.current == null) {
        lastPlaybackTickRef.current = now
        return
      }

      const elapsedSeconds = (now - lastPlaybackTickRef.current) / 1000
      lastPlaybackTickRef.current = now

      if (elapsedSeconds > 0 && elapsedSeconds < 5) {
        listenedSecondsRef.current += elapsedSeconds
      }
    }, 1000)

    return () => {
      clearInterval(intervalId)
    }
  }, [selectedTrack, isPlaying])

  useEffect(() => {
    setTracksPage(1);
  }, [searchQuery, selectedArtist, selectedAlbum, activeView]);
  
  useEffect(() => {
    setArtistsPage(1);
  }, [searchQuery, activeView]);

  useEffect(() => {
    if (!currentUser) return;
    async function fetchLikedState() {
      if (!selectedTrack) {
        setIsCurrentTrackLiked(false);
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/playlists/liked-songs/tracks/${selectedTrack.id}`, {
            credentials: "include"
          }
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
  }, [currentUser, selectedTrack]);

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

  useEffect(() => {
    if (!currentUser) return;
    async function fetchArtistGenres() {
      if (!selectedArtist) {
        setSelectedArtistGenres([]);
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/artists/${encodeURIComponent(selectedArtist)}/genres`, {
            credentials: "include"
          }
        );

        if (!response.ok) {
          throw new Error("Failed to fetch artist genres");
        }

        const data = await response.json();
        setSelectedArtistGenres(data);
      } catch (error) {
        console.error(error);
        setSelectedArtistGenres([]);
      }
    }

    fetchArtistGenres();
  }, [currentUser, selectedArtist]);

  function handleTrackClick(track){
    if (
      selectedTrack &&
      selectedTrack.id !== track.id &&
      audioRef.current &&
      !audioRef.current.ended
    ) {
      sendSkipEvent(selectedTrack);
    }
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
    setSelectedGenre(null);
    setSearchQuery("")
    setActiveView("tracks")
  }
  function handleAlbumClick(album) {
    setSelectedAlbum(album)
    setSelectedArtist(null)
    setSelectedGenre(null);
    setSearchQuery("")
    setActiveView("tracks")
  }
  function handleGenreClick(genre) {
    setSelectedGenre(genre);
    setSelectedArtist(null);
    setSelectedAlbum(null);
    setSearchQuery("");
    setActiveView("tracks");
  }
  function handleClearFilters() {
    setSelectedArtist(null);
    setSelectedAlbum(null)
    setSelectedGenre(null);
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

    if (selectedTrack && audioRef.current && audioRef.current.currentTime > 0 && !audioRef.current.ended) {
      sendSkipEvent(selectedTrack);
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

    if (selectedTrack && audioRef.current && !audioRef.current.ended) {
      sendSkipEvent(selectedTrack);
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
    setIsPlaying(true);
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

  async function handleSetupAdmin(username, password) {
    setAuthError("");

    const response = await fetch(`${API_BASE_URL}/api/auth/setup-admin`, {
      credentials: "include",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Unable to create admin account");
    }

    setSetupRequired(false);
    setCurrentUser(data.user);
  }

  async function handleLogin(username, password) {
    setAuthError("");

    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      credentials: "include",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Unable to sign in");
    }

    setCurrentUser(data.user);
  }

  async function handleLogout() {
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });

    setCurrentUser(null);
  }

  async function handleCreatePlaylist() {
    const trimmedName = newPlaylistName.trim();

    if (!trimmedName) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/playlists`, {
        credentials: "include",
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
          credentials: "include",
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
          credentials: "include",
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

  async function handlePlayPlaylist(playlist) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${playlist.id}/tracks`, {
          credentials: "include"
        }
      );

      if (!response.ok) {
        throw new Error("Failed to fetch playlist tracks");
      }

      const tracksData = await response.json();

      if (!tracksData.length) {
        return;
      }

      setSelectedPlaylist(playlist);
      setPlaylistTracks(tracksData);
      setActiveView("playlist");
      setSelectedArtist(null);
      setSelectedAlbum(null);
      setSelectedGenre(null);
      setSearchQuery("");

      setOriginalQueue(tracksData);
      setQueue(tracksData);
      setQueueIndex(0);
      setSelectedTrack(tracksData[0]);
      setIsPlaying(true);
      setOpenPlaylistMenuId(null);
    } catch (error) {
      console.error(error);
    }
  }

  async function handlePlaylistClick(playlist) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${playlist.id}/tracks`,{
          credentials: "include"
        }
      );

      if (!response.ok) {
        throw new Error("Failed to fetch playlist tracks");
      }

      const tracksData = await response.json();

      setSelectedPlaylist(playlist);
      setPlaylistTracks(tracksData);
      setSelectedArtist(null);
      setSelectedAlbum(null);
      setSelectedGenre(null);
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
          credentials: "include",
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
          credentials: "include",
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
        credentials: "include",
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
      setSelectedGenre(null);

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
        credentials: "include",
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to scan library");
      }

      const scanResult = await response.json();

      const [tracksResponse, artistsResponse, albumsResponse, playlistsResponse, lastfmReadinessResponse] =
        await Promise.all([
          fetch(`${API_BASE_URL}/api/tracks`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/artists`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/albums`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/playlists`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/settings/lastfm/readiness`, { credentials: "include" })
        ]);

      if (
        !tracksResponse.ok ||
        !artistsResponse.ok ||
        !albumsResponse.ok ||
        !playlistsResponse.ok ||
        !lastfmReadinessResponse.ok
      ) {
        throw new Error("Failed to refresh library after scan");
      }

      const tracksData = await tracksResponse.json();
      const artistsData = await artistsResponse.json();
      const albumsData = await albumsResponse.json();
      const playlistsData = await playlistsResponse.json();
      const lastfmReadinessData = await lastfmReadinessResponse.json();

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
      setLastfmReadiness(lastfmReadinessData);
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
        credentials: "include",
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          cleanup_enabled: appSettings.cleanup_enabled,
          cleanup_time: appSettings.cleanup_time || null,
          scan_enabled: appSettings.scan_enabled,
          scan_time: appSettings.scan_time || null,
          lastfm_api_key: lastfmApiKey.trim() || null,
          lastfm_api_secret: lastfmApiSecret.trim() || null,
          lastfm_username: lastfmUsername || null,
          lastfm_session_key: lastfmSessionKey || null,
          lastfm_enrichment_enabled: appSettings.lastfm_enrichment_enabled,
          lastfm_enrichment_time: appSettings.lastfm_enrichment_time || null,
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
      setLastfmApiKey(savedSettings.lastfm_api_key || "");
      setLastfmApiSecret(savedSettings.lastfm_api_secret || "")
      setLastfmUsername(savedSettings.lastfm_username || "")
      setLastfmSessionKey(savedSettings.lastfm_session_key || "")
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
          credentials: "include",
          method: "POST",
        }
      );

      if (!cleanupResponse.ok) {
        throw new Error("Failed to run cleanup");
      }

      const cleanupResult = await cleanupResponse.json();

      const [tracksResponse, artistsResponse, albumsResponse, playlistsResponse] =
        await Promise.all([
          fetch(`${API_BASE_URL}/api/tracks`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/artists`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/albums`, { credentials: "include" }),
          fetch(`${API_BASE_URL}/api/playlists`, { credentials: "include" }),
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
  
    const track = selectedTrack;
    const wasLiked = isCurrentTrackLiked;
  
    try {
      const response = await fetch(
        wasLiked
          ? `${API_BASE_URL}/api/playlists/liked-songs/tracks/${track.id}`
          : `${API_BASE_URL}/api/playlists/liked-songs/tracks`,
        wasLiked
          ? {
              credentials: "include",
              method: "DELETE",
            }
          : {
              credentials: "include",
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ track_id: track.id }),
            }
      );
    
      if (!response.ok) {
        throw new Error("Failed to toggle liked track");
      }
    
      const data = await response.json();
      setIsCurrentTrackLiked(data.liked);
    
      await postListeningEvent(
        track.id,
        wasLiked ? "unlike" : "like",
        {
          position_seconds: audioRef.current?.currentTime ?? currentTime ?? 0,
          duration_seconds: audioRef.current?.duration || duration || null,
        }
      );
    
      if (selectedPlaylist?.system_key === "liked_songs") {
        const likedSongsResponse = await fetch(
          `${API_BASE_URL}/api/playlists/${selectedPlaylist.id}/tracks`, {
            credentials: "include"
          }
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
    setEditTrackGenres((track.genres || []).join(", "));
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
    setEditTrackGenres("");
    setIsArtistMenuOpen(false);
    setIsCreatingArtist(false);
    setNewArtistName("");
    setIsAlbumMenuOpen(false);
    setIsCreatingAlbum(false);
    setNewAlbumName("");
  }

  function handleUseRawMetadata() {
    if (!editingTrack) {
      return;
    }

    setEditTrackTitle(editingTrack.raw_title || "");
    setEditTrackArtist(editingTrack.raw_artist || "");
    setEditTrackAlbum(editingTrack.raw_album || "");
    setEditTrackGenres(
      editingTrack.raw_genre
        ? editingTrack.raw_genre
        : (editingTrack.genres || []).join(", ")
    );
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
    const parsedGenres = editTrackGenres
      .split(",")
      .map((genre) => genre.trim())
      .filter(Boolean);

    if (!trimmedTitle) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/tracks/${editingTrack.id}`,
        {
          credentials: "include",
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title: trimmedTitle,
            artist: trimmedArtist || null,
            album: trimmedAlbum || null,
            genres: parsedGenres
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
    setArtistArtworkFile(null);
    setArtistArtworkPreviewUrl(
      selectedArtistArtworkPath ? `${API_BASE_URL}${selectedArtistArtworkPath}` : ""
    );

    setEditingArtistName(selectedArtist);
    setTransferArtistTarget("");
    setIsArtistActionsOpen(false);
    setIsEditArtistModalOpen(true);
    setIsTransferArtistMenuOpen(false);
  }

  function handleArtistArtworkFileChange(event) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setArtistArtworkFile(file);
    setArtistArtworkPreviewUrl(URL.createObjectURL(file));
  }

  async function handleSaveArtistArtwork(artistName) {
    if (!artistName || !artistArtworkFile) {
      return null;
    }

    const formData = new FormData();
    formData.append("file", artistArtworkFile);

    const response = await fetch(
      `${API_BASE_URL}/api/artists/${encodeURIComponent(artistName)}/artwork`,
      {
        credentials: "include",
        method: "POST",
        body: formData,
      }
    );

    if (!response.ok) {
      throw new Error("Failed to upload artist artwork");
    }

    return response.json();
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
            credentials: "include",
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
            credentials: "include",
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
        fetch(`${API_BASE_URL}/api/tracks`, { credentials: "include" }),
        fetch(`${API_BASE_URL}/api/artists`, { credentials: "include" }),
        fetch(`${API_BASE_URL}/api/albums`, { credentials: "include" }),
        fetch(`${API_BASE_URL}/api/playlists`, { credentials: "include" }),
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
      if (artistArtworkFile) {
        const artworkResult = await handleSaveArtistArtwork(currentSourceArtist);
        setSelectedArtistArtworkPath(artworkResult?.artwork_path || "");
      }
      handleCloseEditArtist();
    } catch (error) {
      console.error(error);
    }
  }

  function handleOpenChangeArtwork(playlist) {
    if (playlist.system_key === "liked_songs") {
      return;
    }

    setArtworkPlaylist(playlist);
    setArtworkFile(null);
    setArtworkPreviewUrl(playlist.artwork_path ? `${API_BASE_URL}${playlist.artwork_path}` :  "");
    setOpenPlaylistMenuId(null);
  }

  function handleCloseChangeArtwork() {
    setArtworkPlaylist(null);
    setArtworkFile(null);
    setArtworkPreviewUrl("");
  }

  function handleArtworkFileChange(event) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setArtworkFile(file);
    setArtworkPreviewUrl(URL.createObjectURL(file));
  }

  async function handleSavePlaylistArtwork() {
    if (!artworkPlaylist || !artworkFile) {
      return;
    }

    try {
      const formData = new FormData();
      formData.append("file", artworkFile);

      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${artworkPlaylist.id}/artwork`,
        {
          credentials: "include",
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error("Failed to upload playlist artwork");
      }

      const updatedPlaylist = await response.json();

      setPlaylists((prev) =>
        prev
          .map((playlist) =>
            playlist.id === updatedPlaylist.id ? updatedPlaylist : playlist
          )
          .sort((a, b) => {
            if (a.system_key === "liked_songs") return -1;
            if (b.system_key === "liked_songs") return 1;
            return a.name.localeCompare(b.name);
          })
      );

      setSelectedPlaylist((prev) =>
        prev?.id === updatedPlaylist.id ? updatedPlaylist : prev
      );

      handleCloseChangeArtwork();
    } catch (error) {
      console.error(error);
    }
  }
  
  function handleRefreshSimilarTracks() {
      setSimilarRefreshKey((prev) => prev + 1);
    }

    async function handleAddSimilarTrackToCurrentPlaylist(track) {
    if (!selectedPlaylist) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/playlists/${selectedPlaylist.id}/tracks`,
        {
          credentials: "include",
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ track_id: track.id }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to add similar track to playlist");
      }

      setPlaylistTracks((prev) => [...prev, track]);
      setSimilarRefreshKey((prev) => prev + 1);
    } catch (error) {
      console.error(error);
    }
  }

  async function handleRunLastfmEnrichment() {
    setLastfmEnrichmentSummary(null)
    setSettingsNotice("Starting Last.fm enrichment...")

    try {
      const response = await fetch(`${API_BASE_URL}/api/settings/lastfm/enrich`, {
        credentials: "include",
        method: "POST",
        cache: "no-store",
      })

      if (!response.ok) {
        throw new Error("Failed to start Last.fm enrichment")
      }

      const result = await response.json()

      if (result.reason === "already_running") {
        setSettingsNotice("Last.fm enrichment is already running.")
        startLastfmProgressPolling()
        await fetchLastfmProgress()
        return
      }

      if (!result.started) {
        throw new Error("Last.fm enrichment did not start")
      }

      setSettingsNotice("Last.fm enrichment started.")
      startLastfmProgressPolling()
      await fetchLastfmProgress()
    } catch (error) {
      console.error(error)
      setSettingsNotice("Failed to start Last.fm enrichment.")
    }
  }

  async function handleStopLastfmEnrichment() {
    try {
      setLastfmProgress((prev) =>
        prev
          ? {
              ...prev,
              is_running: true,
              is_stopping: true,
              is_stopped: false,
              last_result: "stop_requested",
            }
          : prev
      )

      await fetch(`${API_BASE_URL}/api/settings/lastfm/stop`, {
        credentials: "include",
        method: "POST",
        cache: "no-store",
      })

      setSettingsNotice("Stopping Last.fm genre enrichment...")
      await fetchLastfmProgress()
    } catch (error) {
      console.error(error)
      setSettingsNotice("Failed to stop enrichment.")
    }
  }

  async function handleConnectLastfm() {
    if (!lastfmApiKey.trim()) {
      setSettingsNotice("Save your Last.fm API key first.")
      return
    }

    setIsLastfmConnecting(true)

    try {
      const callbackUrl = `${window.location.origin}/settings/lastfm/callback`

      const response = await fetch(
        `${API_BASE_URL}/api/settings/lastfm/auth-url?callback_url=${encodeURIComponent(callbackUrl)}`,{
          credentials: "include"
        }
      )

      if (!response.ok) {
        throw new Error("Failed to get Last.fm auth URL")
      }

      const data = await response.json()

      if (!data.auth_url) {
        throw new Error("Missing Last.fm auth URL")
      }

      window.location.href = data.auth_url
    } catch (error) {
      console.error(error)
      setSettingsNotice("Failed to start Last.fm connection.")
      setIsLastfmConnecting(false)
    }
  }

  function startMusicbrainzReadinessPolling() {
    if (musicbrainzReadinessIntervalRef.current) {
      return
    }
  
    fetchMusicbrainzReadiness()
  
    musicbrainzReadinessIntervalRef.current = window.setInterval(() => {
      fetchMusicbrainzReadiness()
    }, 2500)
  }
  
  function stopMusicbrainzReadinessPolling() {
    if (musicbrainzReadinessIntervalRef.current) {
      clearInterval(musicbrainzReadinessIntervalRef.current)
      musicbrainzReadinessIntervalRef.current = null
    }
  }

  async function handleResumeMusicbrainzTagging() {
    try {
      setIsResumingMusicbrainz(true)

      const response = await fetch(`${API_BASE_URL}/api/settings/musicbrainz/resume`, {
        credentials: "include",
        method: "POST",
      })

      if (!response.ok) {
        throw new Error("Failed to resume MusicBrainz tagging")
      }

      const result = await response.json()

      if (result.reason === "already_running") {
        setSettingsNotice("MusicBrainz tagging is already running.")
      } else if (result.reason === "nothing_to_resume") {
        setSettingsNotice("No unfinished MusicBrainz tagging work was found.")
      } else if (result.started) {
        setSettingsNotice("MusicBrainz tagging resumed.")
        startMusicbrainzReadinessPolling()
      } else {
        setSettingsNotice("MusicBrainz tagging could not be resumed.")
      }

      const readinessResponse = await fetch(`${API_BASE_URL}/api/settings/lastfm/readiness`,{
        credentials: "include"
      })
      if (readinessResponse.ok) {
        const readinessData = await readinessResponse.json()
        setLastfmReadiness(readinessData)
      }
    } catch (error) {
      console.error(error)
      setSettingsNotice("Failed to resume MusicBrainz tagging.")
      setIsResumingMusicbrainz(false)
    }
  }

  function handleOpenChangeAlbumArtwork(albumName) {
    setArtworkAlbum(albumName);
    setAlbumArtworkFile(null);

    const currentArtwork = albumArtworkMap[albumName];

    setAlbumArtworkPreviewUrl(
      currentArtwork ? `${API_BASE_URL}${currentArtwork}` : ""
    );
  }

  function handleCloseChangeAlbumArtwork() {
    setArtworkAlbum(null);
    setAlbumArtworkFile(null);
    setAlbumArtworkPreviewUrl("");
  }

  function handleAlbumArtworkFileChange(event) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setAlbumArtworkFile(file);
    setAlbumArtworkPreviewUrl(URL.createObjectURL(file));
  }

  async function handleSaveAlbumArtwork() {
    if (!artworkAlbum || !albumArtworkFile) {
      return;
    }

    const albumBeingEdited = artworkAlbum;

    try {
      const formData = new FormData();
      formData.append("file", albumArtworkFile);

      const response = await fetch(
        `${API_BASE_URL}/api/albums/${encodeURIComponent(albumBeingEdited)}/artwork`,
        {
          credentials: "include",
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error("Failed to upload album artwork");
      }

      const result = await response.json();
      const nextArtworkPath = result.artwork_path || "";

      setAlbumArtworkMap((prev) => ({
        ...prev,
        [getAlbumKey(albumBeingEdited)]: nextArtworkPath
          ? `${nextArtworkPath}?v=${Date.now()}`
          : "",
      }));

      handleCloseChangeAlbumArtwork();
    } catch (error) {
      console.error(error);
    }
  }

  async function fetchLastfmProgress() {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/settings/lastfm/progress?_=${Date.now()}`,
        {
          credentials: "include",
          method: "GET",
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache",
            Pragma: "no-cache",
          },
        }
      )

      if (!response.ok) {
        throw new Error("Failed to fetch Last.fm progress")
      }

      const data = await response.json()

      setLastfmProgress(data)
      setIsLastfmEnriching(data.is_running || data.is_stopping)

      if (!data.is_running && !data.is_stopping && lastfmProgressIntervalRef.current) {
        clearInterval(lastfmProgressIntervalRef.current)
        lastfmProgressIntervalRef.current = null
      }
    } catch (error) {
      console.error(error)

      if (lastfmProgressIntervalRef.current) {
        clearInterval(lastfmProgressIntervalRef.current)
        lastfmProgressIntervalRef.current = null
      }
    }
  }

  async function fetchMusicbrainzReadiness() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/settings/lastfm/readiness`, {
        credentials: "include",
        cache: "no-store",
      })

      if (!response.ok) {
        throw new Error("Failed to fetch MusicBrainz readiness")
      }

      const data = await response.json()
      setLastfmReadiness(data)

      if (!data.musicbrainz_backfill_running && musicbrainzReadinessIntervalRef.current)  {
        clearInterval(musicbrainzReadinessIntervalRef.current)
        musicbrainzReadinessIntervalRef.current = null
        setIsResumingMusicbrainz(false)
      }
    } catch (error) {
      console.error(error)

      if (musicbrainzReadinessIntervalRef.current) {
        clearInterval(musicbrainzReadinessIntervalRef.current)
        musicbrainzReadinessIntervalRef.current = null
      }

      setIsResumingMusicbrainz(false)
    }
  }

  async function sendLastfmNowPlaying(trackId) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/tracks/${trackId}/lastfm/now-playing`,
        {
          credentials: "include",
          method: "POST",
        }
      )

      if (!response.ok) {
        throw new Error("Failed to update Last.fm now playing")
      }

      const data = await response.json()
      console.log("Last.fm now playing updated:", data)
    } catch (error) {
      console.error(error)
    }
  }

  async function sendLastfmScrobble(trackId) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/tracks/${trackId}/lastfm/scrobble`,
        {
          credentials: "include",
          method: "POST",
        }
      )

      if (!response.ok) {
        throw new Error("Failed to scrobble track to Last.fm")
      }

      const data = await response.json()
      console.log("Last.fm scrobbled:", data)
    } catch (error) {
      console.error(error)
    }
  }

  async function fetchStatsOverview() {
    try {
      setIsLoadingStatsOverview(true);

      const response = await fetch(`${API_BASE_URL}/api/stats/overview`,{
        credentials: "include"
      });

      if (!response.ok) {
        throw new Error("Failed to fetch stats overview");
      }

      const data = await response.json();
      setStatsOverview(data);
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoadingStatsOverview(false);
    }
  }

  useEffect(() => {
    if (!currentUser) return;
    if (!selectedTrack || !isPlaying) {
      return
    }

    if (lastScrobbledTrackIdRef.current === selectedTrack.id) {
      return
    }

    if (listenedSecondsRef.current < 40) {
      return
    }

    lastScrobbledTrackIdRef.current = selectedTrack.id
    sendLastfmScrobble(selectedTrack.id)
  }, [currentUser, selectedTrack, isPlaying, currentTime])

  function startLastfmProgressPolling() {
    if (lastfmProgressIntervalRef.current) {
      return
    }
  
    fetchLastfmProgress()
  
    lastfmProgressIntervalRef.current = window.setInterval(() => {
      fetchLastfmProgress()
    }, 4000)
  }

  function stopLastfmProgressPolling() {
    if (lastfmProgressIntervalRef.current) {
      clearInterval(lastfmProgressIntervalRef.current)
      lastfmProgressIntervalRef.current = null
    }
  }

  function getPlaylistArtwork(playlist) {
    if (playlist.system_key === "liked_songs") {
      return {
        type: "image",
        src: "/liked-songs.png",
      };
    }

    if (playlist.artwork_path) {
      return {
        type: "image",
        src: `${API_BASE_URL}${playlist.artwork_path}`,
      };
    }

    return {
      type: "generated",
      initials: getPlaylistInitials(playlist.name),
      gradientClass: getPlaylistGradientClass(playlist.name),
    };
  }
  function getAlbumKey(albumName) {
    return (albumName || "").trim();
  }

  function getAlbumArtwork(albumName) {
    const albumKey = getAlbumKey(albumName);
    const artworkPath = albumArtworkMap[albumKey];

    if (artworkPath) {
      return {
        type: "image",
        src: `${API_BASE_URL}${artworkPath}`,
      };
    }

    return {
      type: "generated",
      initials: getPlaylistInitials(albumName),
      gradientClass: getPlaylistGradientClass(albumName),
    };
  }

  function getPlaylistInitials(name) {
    if (!name) return "♪";

    const words = name.trim().split(/\s+/).slice(0, 2);
    return words.map((word) => word[0]?.toUpperCase() || "").join("");
  }

  function getPlaylistGradientClass(name) {
    const gradients = [
      "playlist-art--gradient-1",
      "playlist-art--gradient-2",
      "playlist-art--gradient-3",
      "playlist-art--gradient-4",
      "playlist-art--gradient-5",
      "playlist-art--gradient-6",
    ];

    let hash = 0;
    for (let index = 0; index < name.length; index += 1) {
      hash = name.charCodeAt(index) + ((hash << 5) - hash);
    }

    return gradients[Math.abs(hash) % gradients.length];
  }

  const visibleTracks = useMemo(() => {
    return tracks.filter((track) => {
      const matchesArtist = selectedArtist
        ? (track.artists?.includes(selectedArtist) || track.artist === selectedArtist)
        : true;
      const matchesAlbum = selectedAlbum ? track.album === selectedAlbum : true;
      const matchesGenre = selectedGenre
        ? (track.genres || []).includes(selectedGenre)
        : true;

      const query = searchQuery.trim().toLowerCase();
      const matchesSearch =
        query === "" ||
        track.title?.toLowerCase().includes(query) ||
        track.artist?.toLowerCase().includes(query) ||
        track.album?.toLowerCase().includes(query) ||
        track.genre?.toLowerCase().includes(query);

      return matchesArtist && matchesAlbum && matchesGenre && matchesSearch;
    });
  }, [tracks, selectedArtist, selectedAlbum, selectedGenre, searchQuery]);

  const shouldShowSimilarSection =
    (activeView === "tracks" && (selectedArtist || selectedAlbum) && !selectedGenre) ||
    activeView === "playlist";

  const similarSourceTrack = useMemo(() => {
    if (!shouldShowSimilarSection) {
      return null;
    }

    const sourceTracks = activeView === "playlist" ? playlistTracks : visibleTracks;

    if (selectedTrack && sourceTracks.some((track) => track.id === selectedTrack.id)) {
      return selectedTrack;
    }

    return sourceTracks[0] || null;
  }, [shouldShowSimilarSection, activeView, playlistTracks, visibleTracks, selectedTrack]);

  useEffect(() => {
    if (!currentUser) return;
    async function fetchSimilar() {
      if (!shouldShowSimilarSection) {
        setSimilarTracks([]);
        return;
      }

      try {
        if (activeView === "playlist" && selectedPlaylist) {
          const res = await fetch(
            `${API_BASE_URL}/api/playlists/${selectedPlaylist.id}/recommendations?debug=true&refresh=${similarRefreshKey}&_=${Date.now()}`,{
              credentials: "include"
            }
          );
        
          if (!res.ok) {
            throw new Error("Failed to fetch playlist recommendations");
          }
        
          const data = await res.json();
        
          const recommendations = (data.recommendations || []).map((item) => ({
            ...item.track,
            debug: item.debug || {},
          }));
        
          setSimilarTracks(recommendations.slice(0, SIMILAR_TRACK_LIMIT));
          return;
        }

        if (!similarSourceTrack) {
          setSimilarTracks([]);
          return;
        }

        const res = await fetch(
          `${API_BASE_URL}/api/tracks/${similarSourceTrack.id}/similar`,{
            credentials: "include"
          }
        );

        if (!res.ok) {
          throw new Error("Failed to fetch similar tracks");
        }

        const data = await res.json();
        setSimilarTracks(data.slice(0, SIMILAR_TRACK_LIMIT));
      } catch (error) {
        console.error(error);
        setSimilarTracks([]);
      }
    }

    fetchSimilar();
  }, [
    currentUser,
    similarSourceTrack,
    shouldShowSimilarSection,
    activeView,
    selectedPlaylist,
    playlistTracks,
    similarRefreshKey,
  ]);



  useEffect(() => {
    return () => {
      stopLastfmProgressPolling()
      stopMusicbrainzReadinessPolling()
    }
  }, [])

  useEffect(() => {
    if (!currentUser) return;
    fetchLastfmProgress()
  }, [currentUser])

  useEffect(() => {
    if (!lastfmProgress) {
      return
    }

    const isActive = lastfmProgress.is_running || lastfmProgress.is_stopping

    if (isActive && !lastfmProgressIntervalRef.current) {
      startLastfmProgressPolling()
    }
  }, [lastfmProgress])

  useEffect(() => {
    if (!currentUser) return;
    if (!selectedTrack || !isPlaying) {
      return
    }

    if (lastNowPlayingTrackIdRef.current === selectedTrack.id) {
      return
    }

    lastNowPlayingTrackIdRef.current = selectedTrack.id
    sendLastfmNowPlaying(selectedTrack.id)
  }, [currentUser, selectedTrack, isPlaying])

  useEffect(() => {
    if (!currentUser) return;
    if (!lastfmReadiness) {
      return
    }

    if (lastfmReadiness.musicbrainz_backfill_running && !musicbrainzReadinessIntervalRef.current) {
      startMusicbrainzReadinessPolling()
    }
  }, [currentUser, lastfmReadiness])

  useEffect(() => {
    if (!currentUser) return;
    async function fetchSelectedArtistArtwork() {
      if (!selectedArtist) {
        setSelectedArtistArtworkPath("");
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/artists/${encodeURIComponent(selectedArtist)}/artwork`,{
            credentials: "include"
          }
        );

        if (!response.ok) {
          throw new Error("Failed to fetch artist artwork");
        }

        const data = await response.json();
        setSelectedArtistArtworkPath(data.artwork_path || "");
      } catch (error) {
        console.error(error);
        setSelectedArtistArtworkPath("");
      }
    }

    fetchSelectedArtistArtwork();
  }, [currentUser, selectedArtist]);

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



  const visibleGenres = useMemo(() => {
    return genres.filter((genre) =>
      genre.toLowerCase().includes(searchQuery.trim().toLowerCase())
    );
  }, [genres, searchQuery]);

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

  useEffect(() => {
    if (!currentUser) return;
    if (activeView !== "artists" || artistViewMode !== "grid") {
      return;
    }

    async function fetchArtistGridArtwork() {
      const artistsToFetch = paginatedArtists.filter(
        (artist) => artistArtworkMap[artist] === undefined
      );

      if (artistsToFetch.length === 0) {
        return;
      }

      try {
        const results = await Promise.all(
          artistsToFetch.map(async (artist) => {
            const response = await fetch(
              `${API_BASE_URL}/api/artists/${encodeURIComponent(artist)}/artwork`,{
                credentials: "include"
              }
            );

            if (!response.ok) {
              return [artist, ""];
            }

            const data = await response.json();
            return [artist, data.artwork_path || ""];
          })
        );

        setArtistArtworkMap((prev) => ({
          ...prev,
          ...Object.fromEntries(results),
        }));
      } catch (error) {
        console.error(error);
      }
    }

    fetchArtistGridArtwork();
  }, [currentUser, activeView, artistViewMode, paginatedArtists, artistArtworkMap]);

  useEffect(() => {
    if (!currentUser) return;
    async function fetchAlbumArtwork() {
      const albumsNeeded = new Set();
    
      if (activeView === "albums") {
        visibleAlbums.slice(0, 80).forEach((album) => {
          if (album) albumsNeeded.add(getAlbumKey(album));
        });
      }
    
      if (selectedAlbum) {
        albumsNeeded.add(getAlbumKey(selectedAlbum));
      }
    
      paginatedTracks.forEach((track) => {
        if (track.album) albumsNeeded.add(getAlbumKey(track.album));
      });
    
      playlistTracks.forEach((track) => {
        if (track.album) albumsNeeded.add(getAlbumKey(track.album));
      });
    
      const albumsToFetch = Array.from(albumsNeeded).filter(
        (album) => album && albumArtworkMap[album] === undefined
      );
    
      if (albumsToFetch.length === 0) return;
    
      try {
        const results = await Promise.all(
          albumsToFetch.map(async (album) => {
            const response = await fetch(
              `${API_BASE_URL}/api/albums/${encodeURIComponent(album)}/artwork`,
              { 
                credentials: "include",
                cache: "no-store"
               }
            );
          
            if (!response.ok) {
              return [album, ""];
            }
          
            const data = await response.json();
            return [album, data.artwork_path || ""];
          })
        );
      
        setAlbumArtworkMap((prev) => ({
          ...prev,
          ...Object.fromEntries(results),
        }));
      } catch (error) {
        console.error("Failed to fetch album artwork", error);
      }
    }
  
    fetchAlbumArtwork();
  }, [
    currentUser,
    activeView,
    visibleAlbums,
    selectedAlbum,
    paginatedTracks,
    playlistTracks,
    albumArtworkMap,
    API_BASE_URL,
  ]);

  const editArtistAlbums = useMemo(() => {
    return albums.filter((album) =>
      tracks.some(
        (track) =>
          (track.artist || "") === editTrackArtist &&
          (track.album || "") === album
      )
    );
  }, [albums, tracks, editTrackArtist]);

  const upcomingQueue = queue.slice(queueIndex + 1);

  const selectedArtistTrackCount = useMemo(() => {
    if (!selectedArtist) {
      return 0;
    }

    return tracks.filter((track) => track.artist === selectedArtist).length;
  }, [tracks, selectedArtist]);

  const selectedArtistAlbumCount = useMemo(() => {
    if (!selectedArtist) {
      return 0;
    }

    return new Set(
      tracks
        .filter((track) => track.artist === selectedArtist && track.album)
        .map((track) => track.album)
    ).size;
  }, [tracks, selectedArtist]);

  const selectedAlbumTrackCount = useMemo(() => {
    if (!selectedAlbum) {
      return 0;
    }

    return tracks.filter((track) => track.album === selectedAlbum).length;
  }, [tracks, selectedAlbum]);

  const selectedAlbumArtistCount = useMemo(() => {
    if (!selectedAlbum) {
      return 0;
    }

    return new Set(
      tracks
        .filter((track) => track.album === selectedAlbum && track.artist)
        .map((track) => track.artist)
    ).size;
  }, [tracks, selectedAlbum]);

  const selectedGenreTrackCount = useMemo(() => {
    if (!selectedGenre) {
      return 0;
    }

    return tracks.filter((track) =>
      (track.genres || []).includes(selectedGenre)
    ).length;
  }, [tracks, selectedGenre]);

  const genreCounts = useMemo(() => {
    const counts = new Map();

    tracks.forEach((track) => {
      const genres = track.genres || [];

      genres.forEach((genre) => {
        counts.set(genre, (counts.get(genre) || 0) + 1);
      });
    });

    return counts;
  }, [tracks]);

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
        <>
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
                <div className="track-row__index-group">
                  <div className="track-row__index">{index + 1}</div>
                    {track.album && getAlbumArtwork(track.album).type === "image" ? (
                      <img
                        className="track-row__album-art"
                        src={getAlbumArtwork(track.album).src}
                        alt={track.album}
                      />
                    ) : (
                      <div className="track-row__album-art track-row__album-art--placeholder">
                        ♪
                      </div>
                    )}
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
                      event.stopPropagation();
                      setOpenMenuTrackId((prev) => (prev === track.id ? null : track.id));
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
          
          {similarSourceTrack && similarTracks.length > 0 && (
            <div className="similar-section">
              <div className="similar-section__header">
                <h3>More like this</h3>
                <button
                  className="similar-section__refresh-button"
                  type="button"
                  onClick={handleRefreshSimilarTracks}
                >
                  ↻
                </button>
              </div>
          
              <div className="similar-section__list">
                {similarTracks.map((track) => (
                  <div key={track.id} className="track-row similar-track-row">
                    <button
                      className="similar-track-row__main"
                      onClick={() => handleTrackClick(track)}
                      type="button"
                    >
                      <div className="track-row__content">
                        <div className="track-row__title">{track.title}</div>
                        <div className="track-row__meta">
                          {track.artist || "Unknown Artist"} • {track.album || "Unknown Album"}
                        </div>
                
                        {track.debug?.reason_summary && (
                          <div className="track-row__reason">
                            {track.debug.reason_summary}
                          </div>
                        )}
                      </div>
                    </button>

                    <button
                      className="similar-track-row__add-button"
                      type="button"
                      onClick={() => handleAddSimilarTrackToCurrentPlaylist(track)}
                      aria-label={`Add ${track.title} to playlist`}
                    >
                      +
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      );
    }

    if (activeView === "insights") {
      const topPlayedCount = statsOverview.top_played.length;
      const mostLikedCount = statsOverview.most_liked.length;
      const mostSkippedCount = statsOverview.most_skipped.length;
      const recentlyPlayedCount = statsOverview.recently_played.length;
    
      return (
        <div className="behavior-insights-page">
          <div className="behavior-insights-hero">
            <h2>Behavior Insights</h2>
            <p>
              See what you play most, skip most, like most, and listened to recently.
            </p>
      
            <button
              className="settings-button settings-button--secondary"
              type="button"
              onClick={fetchStatsOverview}
              disabled={isLoadingStatsOverview}
            >
              {isLoadingStatsOverview ? "Refreshing..." : "Refresh insights"}
            </button>
          </div>
      
          <div className="behavior-insights-summary">
            <div className="behavior-insights-stat">
              <div className="behavior-insights-stat__label">Top Played</div>
              <div className="behavior-insights-stat__value">{topPlayedCount}</div>
            </div>
      
            <div className="behavior-insights-stat">
              <div className="behavior-insights-stat__label">Most Loved</div>
              <div className="behavior-insights-stat__value">{mostLikedCount}</div>
            </div>
      
            <div className="behavior-insights-stat">
              <div className="behavior-insights-stat__label">Most Skipped</div>
              <div className="behavior-insights-stat__value">{mostSkippedCount}</div>
            </div>
      
            <div className="behavior-insights-stat">
              <div className="behavior-insights-stat__label">Recently Played</div>
              <div className="behavior-insights-stat__value">{recentlyPlayedCount}</div>
            </div>
          </div>
      
          <div className="behavior-insights-grid">
            <div className="insights-card">
              <div className="insights-card__header">
                <h3>Top Played</h3>
              </div>
      
              <div className="insights-card__list">
                {statsOverview.top_played.length === 0 ? (
                  <div className="insights-empty">No listening data yet.</div>
                ) : (
                  statsOverview.top_played.slice(0, 5).map((track) => (
                    <button
                      key={`top-played-${track.id}`}
                      className="track-row"
                      type="button"
                      onClick={() => handleTrackClick(track)}
                    >
                      <div className="track-row__content">
                        <div className="track-row__title">{track.title}</div>
                        <div className="track-row__meta">
                          {track.artist || "Unknown Artist"}
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
              
            <div className="insights-card">
              <div className="insights-card__header">
                <h3>Most Loved</h3>
              </div>
              
              <div className="insights-card__list">
                {statsOverview.most_liked.length === 0 ? (
                  <div className="insights-empty">No listening data yet.</div>
                ) : (
                  statsOverview.most_liked.slice(0, 5).map((track) => (
                    <button
                      key={`most-liked-${track.id}`}
                      className="track-row"
                      type="button"
                      onClick={() => handleTrackClick(track)}
                    >
                      <div className="track-row__content">
                        <div className="track-row__title">{track.title}</div>
                        <div className="track-row__meta">
                          {track.artist || "Unknown Artist"}
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
              
            <div className="insights-card">
              <div className="insights-card__header">
                <h3>Most Skipped</h3>
              </div>
              
              <div className="insights-card__list">
                {statsOverview.most_skipped.length === 0 ? (
                  <div className="insights-empty">No listening data yet.</div>
                ) : (
                  statsOverview.most_skipped.slice(0, 5).map((track) => (
                    <button
                      key={`most-skipped-${track.id}`}
                      className="track-row"
                      type="button"
                      onClick={() => handleTrackClick(track)}
                    >
                      <div className="track-row__content">
                        <div className="track-row__title">{track.title}</div>
                        <div className="track-row__meta">
                          {track.artist || "Unknown Artist"}
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
              
            <div className="insights-card">
              <div className="insights-card__header">
                <h3>Recently Played</h3>
              </div>
              
              <div className="insights-card__list">
                {statsOverview.recently_played.length === 0 ? (
                  <div className="insights-empty">No listening data yet.</div>
                ) : (
                  statsOverview.recently_played.slice(0, 5).map((track) => (
                    <button
                      key={`recently-played-${track.id}`}
                      className="track-row"
                      type="button"
                      onClick={() => handleTrackClick(track)}
                    >
                      <div className="track-row__content">
                        <div className="track-row__title">{track.title}</div>
                        <div className="track-row__meta">
                          {track.artist || "Unknown Artist"}
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      );
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
            <div className="settings-card__title">Last.fm Integration</div>
            <div className="settings-card__text">
              Paste your Last.fm API key and shared secret, press "Save settings", then press "Connect Last.fm", to enable genre-tag enrichment from Last.fm and scrobbling. Only do this, once your library scan import and Music Brainz tagging is complete.
            </div>

            <label className="settings-field">
              <span className="settings-field__label">Last.fm API key</span>
              <input
                className="settings-text-input"
                type="text"
                value={lastfmApiKey}
                onChange={(event) => setLastfmApiKey(event.target.value)}
                placeholder="Enter Last.fm API key"
              />
            </label>

            <label className="settings-field">
              <span className="settings-field__label">Last.fm API secret</span>
              <input
                className="settings-text-input"
                type="text"
                value={lastfmApiSecret}
                onChange={(event) => setLastfmApiSecret(event.target.value)}
                placeholder="Enter Last.fm API secret"
              />
            </label>
            <div className="settings-card__text">
              <p></p>
              {lastfmUsername
                ? `Connected as ${lastfmUsername}`
                : "Not connected to Last.fm yet."}
            </div>
            <div className="settings-card__actions">
              <button
                className="settings-button settings-button--secondary"
                type="button"
                onClick={handleConnectLastfm}
                disabled={isLastfmConnecting || !lastfmApiKey.trim() || !lastfmApiSecret.trim()}
              >
                {isLastfmConnecting ? "Connecting..." : "Connect Last.fm"}
              </button>

              {lastfmReadiness.ready && (
                <button
                  className="settings-button"
                  type="button"
                  onClick={handleRunLastfmEnrichment}
                  disabled={isLastfmEnriching || !lastfmApiKey.trim()}
                >
                  {isLastfmEnriching ? "Enriching..." : "Start Last.fm enrichment"}
                </button>
              )}

              {isLastfmEnriching && (
                <button
                  className="settings-button settings-button--danger"
                  type="button"
                  onClick={handleStopLastfmEnrichment}
                >
                  Stop
                </button>
              )}
            </div>
            
            {!lastfmReadiness.ready && (
              <div className="lastfm-readiness-card">
                <div className="lastfm-readiness-card__title">
                  {lastfmReadiness.musicbrainz_backfill_running
                    ? "MusicBrainz tagging is running"
                    : "Waiting for MusicBrainz tagging to finish"}
                </div>
            
                <div className="lastfm-readiness-card__text">
                  Last.fm genre enrichment becomes available once every scanned track has been processed for
                  MusicBrainz recording IDs.
                </div>
            
                <div className="lastfm-readiness-card__bar">
                  <div
                    className="lastfm-readiness-card__bar-fill"
                    style={{ width: `${lastfmReadiness.progress_percent || 0}%` }}
                  />
                </div>
            
                <div className="lastfm-readiness-card__stats">
                  <div className="lastfm-readiness-card__stat">
                    <span className="lastfm-readiness-card__label">Tagged</span>
                    <span className="lastfm-readiness-card__value">
                      {lastfmReadiness.tracks_with_mbid}
                    </span>
                  </div>
            
                  <div className="lastfm-readiness-card__stat">
                    <span className="lastfm-readiness-card__label">Remaining</span>
                    <span className="lastfm-readiness-card__value">
                      {lastfmReadiness.tracks_missing_mbid}
                    </span>
                  </div>
            
                  <div className="lastfm-readiness-card__stat">
                    <span className="lastfm-readiness-card__label">Total</span>
                    <span className="lastfm-readiness-card__value">
                      {lastfmReadiness.total_tracks}
                    </span>
                  </div>
            
                  <div className="lastfm-readiness-card__stat">
                    <span className="lastfm-readiness-card__label">Progress</span>
                    <span className="lastfm-readiness-card__value">
                      {lastfmReadiness.progress_percent}%
                    </span>
                  </div>
                </div>
              {lastfmReadiness.musicbrainz_resume_available &&
                !lastfmReadiness.musicbrainz_backfill_running &&
                !isResumingMusicbrainz && (
                  <div className="lastfm-readiness-card__actions">
                    <button
                      className="settings-button settings-button--secondary"
                      type="button"
                      onClick={handleResumeMusicbrainzTagging}
                    >
                      Resume MusicBrainz tagging
                    </button>
                  </div>
              )}
              </div>
            )}

            {lastfmProgress && (
              <div className="lastfm-readiness-card">
                <div className="lastfm-progress-card__header">
                  <span
                    className={`lastfm-status-pill ${
                      lastfmProgress.is_stopping
                        ? "lastfm-status-pill--stopping"
                        : lastfmProgress.is_running
                        ? "lastfm-status-pill--running"
                        : lastfmProgress.is_stopped
                        ? "lastfm-status-pill--stopped"
                        : "lastfm-status-pill--idle"
                    }`}
                  >
                    {lastfmProgress.is_stopping
                      ? "Stopping..."
                      : lastfmProgress.is_running
                      ? "Running"
                      : lastfmProgress.is_stopped
                      ? "Stopped"
                      : "Idle"}
                  </span>
                    
                  <span className="lastfm-progress-card__batch">
                    Batch {lastfmProgress.current_batch || 0}
                  </span>
                </div>
                    
                <div className="lastfm-readiness-card__title">
                  Last.fm enrichment progress
                </div>
                    
                <div className="lastfm-readiness-card__text">
                  Pulling genre tags, similar tracks, and similar artists from Last.fm.
                </div>
                    
                <div className="lastfm-readiness-card__bar">
                  <div
                    className="lastfm-readiness-card__bar-fill"
                    style={{ width: `${getLastfmProgressPercent()}%` }}
                  />
                </div>
                    
                <div className="lastfm-readiness-card__stats">
                  <div className="lastfm-readiness-card__stat">
                    <span className="lastfm-readiness-card__label">Processed</span>
                    <span className="lastfm-readiness-card__value">
                      {lastfmProgress.processed_tracks || 0}
                    </span>
                  </div>
                    
                  <div className="lastfm-readiness-card__stat">
                    <span className="lastfm-readiness-card__label">Remaining</span>
                    <span className="lastfm-readiness-card__value">
                      {Math.max(
                        (lastfmProgress.total_tracks || 0) -
                          (lastfmProgress.processed_tracks || 0),
                        0
                      )}
                    </span>
                  </div>
                    
                  <div className="lastfm-readiness-card__stat">
                    <span className="lastfm-readiness-card__label">Total</span>
                    <span className="lastfm-readiness-card__value">
                      {lastfmProgress.total_tracks || 0}
                    </span>
                  </div>
                    
                  <div className="lastfm-readiness-card__stat">
                    <span className="lastfm-readiness-card__label">Progress</span>
                    <span className="lastfm-readiness-card__value">
                      {getLastfmProgressPercent()}%
                    </span>
                  </div>
                </div>
                    
                <div className="lastfm-progress-card__track">
                  <span className="lastfm-progress-card__label">Current track</span>
                  <div className="lastfm-progress-card__value">
                    {lastfmProgress.current_title
                      ? `${lastfmProgress.current_index}/${lastfmProgress.current_total} — ${lastfmProgress.current_title}`
                      : "None"}
                  </div>
                </div>
                    
                <div className="lastfm-progress-grid">
                  <div className="lastfm-progress-stat">
                    <div className="lastfm-progress-stat__label">Tagged</div>
                    <div className="lastfm-progress-stat__value">
                      {lastfmProgress.total_processed || 0}
                    </div>
                  </div>
                    
                  <div className="lastfm-progress-stat">
                    <div className="lastfm-progress-stat__label">Skipped</div>
                    <div className="lastfm-progress-stat__value">
                      {lastfmProgress.total_skipped || 0}
                    </div>
                  </div>
                    
                  <div className="lastfm-progress-stat">
                    <div className="lastfm-progress-stat__label">Checked</div>
                    <div className="lastfm-progress-stat__value">
                      {lastfmProgress.total_checked || 0}
                    </div>
                  </div>
                </div>
                    
                <div className="lastfm-progress-card__footer">
                  <span className="lastfm-progress-card__label">Last result</span>
                  <span className="lastfm-progress-card__result">
                    {lastfmProgress.last_result || "None"}
                  </span>
                </div>
              </div>
            )}

            {lastfmEnrichmentSummary && (
              <div className="lastfm-summary">
                <span className="lastfm-summary__item">
                  Processed: {lastfmEnrichmentSummary.total_processed}
                </span>
                <span className="lastfm-summary__item">
                  Skipped: {lastfmEnrichmentSummary.total_skipped}
                </span>
                <span className="lastfm-summary__item">
                  Checked: {lastfmEnrichmentSummary.total_checked}
                </span>
              </div>
            )}

            <label className="settings-field settings-field--inline">
              <input
                type="checkbox"
                checked={appSettings.lastfm_enrichment_enabled}
                onChange={() => handleSettingsToggle("lastfm_enrichment_enabled")}
              />
              <span>Enable daily Last.fm enrichment</span>
            </label>

            <label className="settings-field">
              <span className="settings-field__label">Run time</span>
              <input
                className="settings-time-input"
                type="time"
                value={appSettings.lastfm_enrichment_time}
                onChange={(event) =>
                  handleSettingsTimeChange("lastfm_enrichment_time", event.target.value)
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
              Save settings
            </button>
            <button className="logout-button" onClick={handleLogout}>
              Sign out
            </button>
          </div>
        </div>
      );
    }
    if (activeView === "artists") {
      return (
        <>
          <div className="view-toggle">
            <button
              className={`view-toggle__button ${
                artistViewMode === "list" ? "view-toggle__button--active" : ""
              }`}
              type="button"
              onClick={() => setArtistViewMode("list")}
            >
              List
            </button>
            
            <button
              className={`view-toggle__button ${
                artistViewMode === "grid" ? "view-toggle__button--active" : ""
              }`}
              type="button"
              onClick={() => setArtistViewMode("grid")}
            >
              Grid
            </button>
          </div>
            
          {artistViewMode === "list" ? (
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
            </div>
          ) : (
            <div className="artist-grid">
              {paginatedArtists.map((artist) => (
                <button
                  key={artist}
                  className="artist-grid-card"
                  onClick={() => handleArtistClick(artist)}
                  type="button"
                >
                  <div className="artist-grid-card__image">
                    {artistArtworkMap[artist] ? (
                      <img
                        className="artist-grid-card__img"
                        src={`${API_BASE_URL}${artistArtworkMap[artist]}`}
                        alt={artist}
                      />
                    ) : (
                      <span>{artist.slice(0, 1).toUpperCase()}</span>
                    )}
                  </div>
              
                  <div className="artist-grid-card__name">{artist}</div>
                </button>
              ))}
            </div>
          )}

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
        </>
      );
    }
    
    if (activeView === "albums") {
      return (
        <div className="simple-list">
          {visibleAlbums.map((album) => {
            const artwork = getAlbumArtwork(album);
          
            return (
              <div key={album} className="album-list-row">
                <button
                  className="album-list-row__main"
                  onClick={() => handleAlbumClick(album)}
                  type="button"
                >
                  {artwork.type === "image" ? (
                    <img
                      className="album-list-row__art"
                      src={artwork.src}
                      alt={album}
                    />
                  ) : (
                    <div className={`album-list-row__art album-list-row__art--generated ${artwork.    gradientClass}`}>
                      <span>{artwork.initials}</span>
                    </div>
                  )}

                  <span className="album-list-row__name">{album}</span>
                </button>
                
                <button
                  className="album-list-row__menu-button"
                  type="button"
                  onClick={() => handleOpenChangeAlbumArtwork(album)}
                  aria-label={`Change artwork for ${album}`}
                >
                  ⋯
                </button>
              </div>
            );
          })}
        </div>
      );
    }
    if (activeView === "genres") {
      return (
        <div className="genre-grid">
          {[...visibleGenres]
            .sort((a, b) => (genreCounts.get(b) || 0) - (genreCounts.get(a) || 0))
            .map((genre) => (
              <button
                key={genre}
                className="genre-card"
                onClick={() => handleGenreClick(genre)}
                type="button"
              >
                <div className="genre-card__title">{genre}</div>
                <div className="genre-card__meta">
                  {genreCounts.get(genre) || 0} tracks
                </div>
              </button>
          ))}
        </div>
      );
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
            <div className="track-row__index-group">
              <div className="track-row__index-group">
                <div className="track-row__index">{index + 1}</div>

                {track.album && getAlbumArtwork(track.album).type === "image" ? (
                  <img
                    className="track-row__album-art"
                    src={getAlbumArtwork(track.album).src}
                    alt={track.album}
                  />
                ) : (
                  <div className="track-row__album-art track-row__album-art--placeholder">
                    ♪
                  </div>
                )}
              </div>
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
        {shouldShowSimilarSection && similarSourceTrack && similarTracks.length > 0 && (
          <div className="similar-section">
            <h3>More like this</h3>
        
            <div className="similar-section__list">
              {similarTracks.map((track) => (
                <button
                  key={track.id}
                  className="track-row"
                  onClick={() => handleTrackClick(track)}
                  type="button"
                >
                  <div className="track-row__content">
                    <div className="track-row__title">{track.title}</div>
                    <div className="track-row__meta">
                      {track.artist || "Unknown Artist"} • {track.album || "Unknown Album"}
                    </div>

                    {track.debug?.reason_summary && (
                      <div className="track-row__reason">
                        {track.debug.reason_summary}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
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
    if (activeView === "genres") {
      return "Genres";
    }
    if (activeView === "playlist" && selectedPlaylist) {
      return selectedPlaylist.name
    }
    if (activeView === "insights") {
      return "Insights";
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
    if (selectedGenre) {
      return selectedGenre;
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
      return `${visibleAlbums.length} albums`;
    }
    if (activeView === "genres") {
      return `${visibleGenres.length} genres`;
    }
    if (activeView === "playlist" && selectedPlaylist) {
      return `${playlistTracks.length} tracks`;
    }
    if (activeView === "insights") {
      return "Your listening behavior and trends";
    }
    if (activeView === "settings") {
      return "App preferences and playback options";
    }
    if (selectedArtist) {
      return `${selectedArtistTrackCount} tracks • ${selectedArtistAlbumCount} albums`;
    }
    if (selectedAlbum) {
      return `${selectedAlbumTrackCount} tracks • ${selectedAlbumArtistCount} artist${
        selectedAlbumArtistCount === 1 ? "" : "s"
      }`;
    }
    if (selectedGenre) {
      return `${selectedGenreTrackCount} tracks`;
    }

    return `${visibleTracks.length} tracks`;
  }
  function getLastfmProgressPercent() {
    return Math.max(0, Math.min(lastfmProgress?.progress_percent || 0, 100));
  }

  function getTrackArtwork(track) {
    if (!track?.album) {
      return null;
    }

    const artwork = getAlbumArtwork(track.album);
    return artwork.type === "image" ? artwork.src : null;
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


  const hasMetadataMismatch =
    editingTrack &&
    (
      (editingTrack.raw_title && editingTrack.raw_title !== editingTrack.title) ||
      (editingTrack.raw_artist && editingTrack.raw_artist !== editingTrack.artist) ||
      (editingTrack.raw_album && editingTrack.raw_album !== editingTrack.album)
    );

  function QueueRow({ index, style }) {
    const track = upcomingQueue[index];
    const actualIndex = queueIndex + 1 + index;

    if (!track) {
      return null;
    }

    return (
      <div style={style}>
        <div className="queue-panel__item queue-panel__item--row">
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
      </div>
    );
  }

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
    return (
      <AuthScreen
        mode="setup"
        error={authError}
        onSubmit={handleSetupAdmin}
      />
    );
  }

  if (!currentUser) {
    return (
      <AuthScreen
        mode="login"
        error={authError}
        onSubmit={handleLogin}
      />
    );
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar__header">
          <img className="logo" src="/Adjacent.svg" alt="Adjacent logo" />
          <div className="sidebar__brand">Adjacent</div>
        </div>

        <nav className="sidebar__nav">
          <div
            className={`playlist-sidebar-item__main ${
              activeView === "tracks" ? "sidebar__link--active" : ""
            }`}
            onClick={() => handleClearFilters()}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                handleClearFilters();
              }
            }}
          >
            <div className="playlist-art-wrapper">
              <img className="playlist-art" src="/tracks.png" alt="Tracks" />
            </div>
          
            <button
              className="playlist-sidebar-item__name-button"
              onClick={handleClearFilters}
              type="button"
            >
              Tracks
            </button>
          </div>
          
          <div
            className={`playlist-sidebar-item__main ${
              activeView === "artists" ? "sidebar__link--active" : ""
            }`}
            onClick={() => {
              setActiveView("artists");
              setSearchQuery("");
              setSelectedArtist(null);
              setSelectedAlbum(null);
              setSelectedGenre(null);
              setSelectedPlaylist(null);
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                setActiveView("artists");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedGenre(null);
                setSelectedPlaylist(null);
              }
            }}
          >
            <div className="playlist-art-wrapper">
              <img className="playlist-art" src="/artists.png" alt="Artists" />
            </div>
          
            <button
              className="playlist-sidebar-item__name-button"
              onClick={() => {
                setActiveView("artists");
                setSearchQuery("");
              }}
              type="button"
            >
              Artists
            </button>
          </div>
            
          <div
            className={`playlist-sidebar-item__main ${
              activeView === "albums" ? "sidebar__link--active" : ""
            }`}
            onClick={() => {
              setActiveView("albums");
              setSearchQuery("");
              setSelectedArtist(null);
              setSelectedAlbum(null);
              setSelectedGenre(null);
              setSelectedPlaylist(null);
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                setActiveView("albums");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedGenre(null);
                setSelectedPlaylist(null);
              }
            }}
          >
            <div className="playlist-art-wrapper">
              <img className="playlist-art" src="/albums.png" alt="Albums" />
            </div>
          
            <button
              className="playlist-sidebar-item__name-button"
              onClick={() => {
                setActiveView("albums");
                setSearchQuery("");
              }}
              type="button"
            >
              Albums
            </button>
          </div>

          <div
            className={`playlist-sidebar-item__main ${
              activeView === "genres" ? "sidebar__link--active" : ""
            }`}
            onClick={() => {
              setActiveView("genres");
              setSearchQuery("");
              setSelectedArtist(null);
              setSelectedAlbum(null);
              setSelectedGenre(null);
              setSelectedPlaylist(null);
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                setActiveView("genres");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedGenre(null);
                setSelectedPlaylist(null);
              }
            }}
          >
            <div className="playlist-art-wrapper">
              <img className="playlist-art" src="/genre.png" alt="Genres" />
            </div>

            <button
              className="playlist-sidebar-item__name-button"
              onClick={() => {
                setActiveView("genres");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedGenre(null);
                setSelectedPlaylist(null);
              }}
              type="button"
            >
              Genres
            </button>
          </div>

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


                    <div
                      className={`playlist-sidebar-item__main ${
                        activeView === "playlist" && selectedPlaylist?.id === playlist.id
                          ? "sidebar__link--active"
                          : ""
                      }`}
                    >
                      <div
                        className="playlist-art-wrapper"
                        onClick={(event) => {
                          event.stopPropagation();
                          handlePlayPlaylist(playlist);
                        }}
                      >
                        {getPlaylistArtwork(playlist).type === "image" ? (
                          <img
                            className="playlist-art"
                            src={getPlaylistArtwork(playlist).src}
                            alt={playlist.name}
                          />
                        ) : (
                          <div
                            className={`playlist-art ${getPlaylistArtwork(playlist).gradientClass}`}
                          >
                            <span className="playlist-art__initials">
                              {getPlaylistArtwork(playlist).initials}
                            </span>
                          </div>
                        )}

                        <div className="playlist-art__overlay"></div>
                      </div>
                      
                      <button
                        className="playlist-sidebar-item__name-button"
                        onClick={() => handlePlaylistClick(playlist)}
                      >
                        {playlist.name}
                      </button>
                    </div>


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
                            onClick={() => handleOpenChangeArtwork(playlist)}
                          >
                            Change Artwork
                          </button>

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
          <div
            className={`playlist-sidebar-item__main ${
              activeView === "insights" ? "sidebar__link--active" : ""
            }`}
          >
            <div
              className="playlist-art-wrapper"
              onClick={() => {
                setActiveView("insights");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedGenre(null);
                setSelectedPlaylist(null);
              }}
            >
              <img
                className="playlist-art"
                src="/insights.png"
                alt="Insights"
              />
            </div>
            
            <button
              className="playlist-sidebar-item__name-button"
              onClick={() => {
                setActiveView("insights");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedGenre(null);
                setSelectedPlaylist(null);
              }}
              type="button"
            >
              Insights
            </button>
          </div>
        </div>

        <div className="sidebar__section">
          <div
            className={`playlist-sidebar-item__main ${
              activeView === "settings" ? "sidebar__link--active" : ""
            }`}
          >
            <div
              className="playlist-art-wrapper"
              onClick={() => {
                setActiveView("settings");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedGenre(null);
                setSelectedPlaylist(null);
              }}
            >
              <img
                className="playlist-art"
                src="/settings.png"
                alt="Settings"
              />
            </div>
            
            <button
              className="playlist-sidebar-item__name-button"
              onClick={() => {
                setActiveView("settings");
                setSearchQuery("");
                setSelectedArtist(null);
                setSelectedAlbum(null);
                setSelectedGenre(null);
                setSelectedPlaylist(null);
              }}
              type="button"
            >
              Settings
            </button>
          </div>
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
                  {activeView === "tracks" && selectedArtist && selectedArtistArtworkPath && (
                    <div className="artist-hero-banner">
                      <img
                        className="artist-hero-banner__image"
                        src={`${API_BASE_URL}${selectedArtistArtworkPath}`}
                        alt={`${selectedArtist} banner`}
                      />
                      <div className="artist-hero-banner__overlay" />
                    </div>
                  )}
                  {activeView === "tracks" && selectedAlbum && getAlbumArtwork(selectedAlbum).type === "image" && (
                    <div className="album-hero">
                      <img
                        className="album-hero__image"
                        src={getAlbumArtwork(selectedAlbum).src}
                        alt={`${selectedAlbum} artwork`}
                      />
                    </div>
                  )}
              <div className="main-content__header-row">
                <div>

                  <h1>{getHeaderTitle()}</h1>
                  {!loading && !error && (
                    <div className="page-header__meta">
                      <p className="main-content__subhead">{getHeaderSubtitle()}</p>
                        {activeView === "tracks" && selectedArtist && selectedArtistGenres.length > 0 && (
                          <div className="genre-badges">
                            {selectedArtistGenres.map((genre) => (
                              <span key={genre} className="genre-badge">
                                {genre}
                              </span>
                            ))}
                          </div>
                        )}
                      {activeView === "tracks" && (selectedArtist || selectedAlbum || selectedGenre) && (
                        <button
                          className="page-header__play-button"
                          type="button"
                          onClick={() => {
                            const sourceTracks = visibleTracks;
                          
                            if (!sourceTracks.length) return;
                          
                            setOriginalQueue(sourceTracks);
                            setQueue(sourceTracks);
                            setQueueIndex(0);
                            setSelectedTrack(sourceTracks[0]);
                            setIsPlaying(true);
                          }}
                        >
                          ▶ Play
                        </button>
                      )}
                    </div>
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
            {activeView !== "settings" && activeView !== "insights" && (
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

              <div className="queue-panel__section queue-panel__section--next">
                <div className="queue-panel__section-title">Next Up</div>

                <div className="queue-panel__list">
                  <List
                    style={{ width: "100%", height: "100%" }}
                    rowCount={upcomingQueue.length}
                    rowHeight={88}
                    rowComponent={QueueRow}
                    rowProps={{}}
                  />
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
              {getTrackArtwork(selectedTrack) ? (
                <img
                  className="player-bar__art"
                  src={getTrackArtwork(selectedTrack)}
                  alt={selectedTrack.album || selectedTrack.title}
                />
              ) : (
                <div className="player-bar__art player-bar__art--placeholder">♪</div>
              )}
        
              <div className="player-bar__track-info">
                <div className="player-bar__title">{selectedTrack.title}</div>
                <div className="player-bar__meta">
                  {selectedTrack.artist || "Unknown Artist"} •{" "}
                  {selectedTrack.album || "Unknown Album"}
                </div>
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
          onPlay={() => {
            setIsPlaying(true);
            if (selectedTrack) {
              sendPlayStartEvent(selectedTrack);
            }
          }}
          onPause={() => setIsPlaying(false)}
          onEnded={async () => {
            if (selectedTrack) {
              await sendPlayCompleteEvent(selectedTrack);
            }
          
            setCurrentTime(0);
          
            if (isLoop && audioRef.current) {
              resetPlaybackEventFlagsForTrack(selectedTrack);
              audioRef.current.currentTime = 0;
              audioRef.current.play();
              setIsPlaying(true);
              return;
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

              <div className="modal__raw-metadata">
                {hasMetadataMismatch && (
                  <div className="modal__metadata-warning">
                    Metadata was modified during import. Review for accuracy.
                  </div>
                )}
                <div className="modal__raw-metadata-title">Original file metadata</div>

                <div className="modal__raw-metadata-row">
                  <span className="modal__raw-metadata-label">Raw title:</span>
                  <span className="modal__raw-metadata-value">
                    {editingTrack.raw_title || "—"}
                  </span>
                </div>

                <div className="modal__raw-metadata-row">
                  <span className="modal__raw-metadata-label">Raw artist:</span>
                  <span className="modal__raw-metadata-value">
                    {editingTrack.raw_artist || "—"}
                  </span>
                </div>

                <div className="modal__raw-metadata-row">
                  <span className="modal__raw-metadata-label">Raw album:</span>
                  <span className="modal__raw-metadata-value">
                    {editingTrack.raw_album || "—"}
                  </span>
                </div>

                <div className="modal__raw-metadata-actions">
                  <button
                    className="settings-button settings-button--secondary"
                    type="button"
                    onClick={handleUseRawMetadata}
                    disabled={
                      !editingTrack.raw_title &&
                      !editingTrack.raw_artist &&
                      !editingTrack.raw_album
                    }
                  >
                    Use raw values
                  </button>
                </div>
              </div>

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

              <label className="modal__field">
                <span className="modal__label">Genres</span>
                <input
                  className="modal__input"
                  type="text"
                  value={editTrackGenres}
                  onChange={(event) => setEditTrackGenres(event.target.value)}
                  placeholder="Pop, Dance"
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
              <div className="modal__raw-metadata">
                <div className="modal__raw-metadata-title">Artist banner artwork</div>

                {artistArtworkPreviewUrl ? (
                  <img
                    className="artist-banner-preview"
                    src={artistArtworkPreviewUrl}
                    alt="Artist banner preview"
                  />
                ) : (
                  <div className="artist-banner-preview artist-banner-preview--empty">
                    No artist artwork selected
                  </div>
                )}

                <div className="modal__file-row">
                  <label className="modal__file-button">
                    Choose image
                    <input
                      className="modal__file-input"
                      type="file"
                      accept="image/*"
                      onChange={handleArtistArtworkFileChange}
                    />
                  </label>
              
                  <span className="modal__file-name">
                    {artistArtworkFile ? artistArtworkFile.name : "No file selected"}
                  </span>
                </div>
              </div>
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
      {artworkPlaylist && (
        <div className="modal-overlay" onClick={handleCloseChangeArtwork}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal__header">
              <h2>Change Artwork</h2>
            </div>
      
            <div className="modal__body">
              <label className="modal__field">
                <span className="modal__label">Upload artwork</span>

                <div className="modal__file-row">
                  <label className="modal__file-button">
                    Choose file
                    <input
                      className="modal__file-input"
                      type="file"
                      accept="image/*"
                      onChange={handleArtworkFileChange}
                    />
                  </label>

                  <span className="modal__file-name">
                    {artworkFile ? artworkFile.name : "No file selected"}
                  </span>
                </div>
              </label>
      
              <div className="modal__field">
                <span className="modal__label">Preview</span>
                {artworkPreviewUrl ? (
                  <img
                    className="playlist-artwork-preview"
                    src={artworkPreviewUrl}
                    alt={`${artworkPlaylist.name} artwork preview`}
                  />
                ) : (
                  <div className="playlist-artwork-preview playlist-artwork-preview--empty">
                    No artwork selected
                  </div>
                )}
              </div>
            </div>
              
            <div className="modal__actions">
              <button
                className="settings-button settings-button--secondary"
                type="button"
                onClick={handleCloseChangeArtwork}
              >
                Cancel
              </button>
              
              <button
                className="settings-button"
                type="button"
                onClick={handleSavePlaylistArtwork}
                disabled={!artworkFile}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    {artworkAlbum && (
      <div className="modal-overlay" onClick={handleCloseChangeAlbumArtwork}>
        <div className="modal" onClick={(event) => event.stopPropagation()}>
          <div className="modal__header">
            <h2>Change Album Artwork</h2>
          </div>

          <div className="modal__body">
            <label className="modal__field">
              <span className="modal__label">Upload artwork</span>

              <div className="modal__file-row">
                <label className="modal__file-button">
                  Choose file
                  <input
                    className="modal__file-input"
                    type="file"
                    accept="image/*"
                    onChange={handleAlbumArtworkFileChange}
                  />
                </label>

                <span className="modal__file-name">
                  {albumArtworkFile ? albumArtworkFile.name : "No file selected"}
                </span>
              </div>
            </label>

            <div className="modal__field">
              <span className="modal__label">Preview</span>
              {albumArtworkPreviewUrl ? (
                <img
                  className="playlist-artwork-preview"
                  src={albumArtworkPreviewUrl}
                  alt={`${artworkAlbum} artwork preview`}
                />
              ) : (
                <div className="playlist-artwork-preview playlist-artwork-preview--empty">
                  No artwork selected
                </div>
              )}
            </div>
          </div>
            
          <div className="modal__actions">
            <button
              className="settings-button settings-button--secondary"
              type="button"
              onClick={handleCloseChangeAlbumArtwork}
            >
              Cancel
            </button>
            
            <button
              className="settings-button"
              type="button"
              onClick={handleSaveAlbumArtwork}
              disabled={!albumArtworkFile}
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

function AuthScreen({ mode, error, onSubmit }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const isSetup = mode === "setup";

  async function handleSubmit(event) {
    event.preventDefault();

    setLocalError("");

    if (!username.trim()) {
      setLocalError("Username is required");
      return;
    }

    if (!password) {
      setLocalError("Password is required");
      return;
    }

    if (isSetup && password.length < 8) {
      setLocalError("Password must be at least 8 characters");
      return;
    }

    try {
      setSubmitting(true);
      await onSubmit(username.trim(), password);
    } catch (error) {
      setLocalError(error.message || "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-logo">Adjacent</div>

        <h1>{isSetup ? "Create admin account" : "Sign in"}</h1>

        <p>
          {isSetup
            ? "No admin account exists yet. Create the first admin account to continue."
            : "Sign in to continue to your music library."}
        </p>

        {(error || localError) && (
          <div className="auth-error">{localError || error}</div>
        )}

        <label>
          Username
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            placeholder="admin"
          />
        </label>

        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={isSetup ? "new-password" : "current-password"}
            type="password"
            placeholder="••••••••"
          />
        </label>

        <button type="submit" disabled={submitting}>
          {submitting
            ? "Please wait..."
            : isSetup
              ? "Create admin"
              : "Sign in"}
        </button>
      </form>
    </div>
  );
}

export default App;