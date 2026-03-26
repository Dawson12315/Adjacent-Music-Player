# Adjacent Music Player

Full-stack Spotify-style music app built with:

- FastAPI (backend)
- React (frontend)
- Local music library via file share

## Environment Variables:

- APP_NAME
- APP_ENV
- DEBUG
- DATABASE_URL
- MUSIC_LIBRARY_PATH

## Current Development Status:
Phase 3: Improved Library Navigation and Music Management

Introduce:
- Playlists tab: Create, Delete, Rename, and persistent Liked Songs Playlist(unchangable name, but editable from play bar via later introduced heart button)

Improvements:
- Queue: persistent in DB
- Currently Playing: persistent in DB
- Artist page: list Albums, then singles
- Albums page: allow reassociation to a new artist and renaming