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
Phase 4: Refining Main App function

Introduce:
- Heart icon: toggle switch in playbar, reflecting if a song is in liked songs or not(if yes, light up, if no stay empty), toggle on also can place currently playing in liked songs.

Current Phase Improvements:
- Hide the create playlist behind a toggle plus symbol, next to playlists section titile
- Queue: persistent in DB
- Currently Playing: persistent in DB
- Currently Playing: scrolls song title, if text is too long

Later Improvements:
- Artist page: list Albums, then singles
- Albums page: allow reassociation to a new artist and renaming
- Artwork as icon for sidebar - playlists: Liked Songs art locked, Customizable art for others
- Artwork for currently playing
- Settings side bar section


## After Main app development:
- Dockerize
- Begin Development of a mobile app for android as a reciever to the docker container(potentially ios after)