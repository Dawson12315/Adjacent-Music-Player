# Operating notes

[← Back to the README](../../README.md)

- **One process.** The backend must run as a single uvicorn process: the login
  rate limiter, the migration's read-only guard and the nightly jobs live in
  memory. Do not add `--workers`; the image does not, and the server logs an
  error at boot if it sees `WEB_CONCURRENCY` above one.
- **Logs.** The compose file caps container logs at three 10 MB files. If you
  run the image some other way, set `--log-opt max-size=10m --log-opt
  max-file=3`, or the Docker log grows for ever. The backend keeps no access
  log; `/api/health` tells you whether the library, the database and ffmpeg
  are all there, and says `degraded` with a 503 when one is not.
- **Several addresses.** `FRONTEND_ORIGIN` takes a comma-separated list when
  the same install is opened by more than one name —
  `FRONTEND_ORIGIN=http://192.168.1.50:5173,http://nas.local:5173`.
- **Watching the folder.** With *Watch folder for new files* on (Settings →
  Automation), the server watches the music mount and imports a new file a
  few seconds after it has finished copying, through the same scanner as the
  nightly scan — one import per album, not per file. On a local disk,
  Unraid's `/mnt/user` or a Synology volume it uses the kernel's file events.
  When the library is a CIFS, NFS or SSHFS mount it checks the folder every
  2 minutes instead, because those mounts only report their own writes;
  `FOLDER_WATCH_POLL_SECONDS` changes the interval and
  `WATCHFILES_FORCE_POLLING=1` forces that mode. The status line under the
  checkboxes says which mode is running. A very large library can run past
  Linux's per-user inotify limit; the watcher then falls back to polling and
  says so — raise the limit on the host with
  `sysctl fs.inotify.max_user_watches=524288` (and persist it in
  `/etc/sysctl.d/`). The watcher ignores deleted files (the daily cleanup
  owns removal) and catches up with a normal scan when it starts. A
  read-only mount (`:ro`) is fine.
- **Lyrics.** Lyrics come from the files (tags and `.lrc`/`.txt` sidecars),
  from an admin's edits, or — with *Generate lyrics* on under Automation —
  from the server's own speech model working on the listener's audio. The
  model is downloaded once into `data/models` (about 300 MB for `base`);
  generation runs in a background transcode slot and never ahead of a
  stream. Nothing is fetched from any lyrics service. Details and the
  licence table are in [Lyrics](../lyrics.md).
- **Cache size.** The transcode caches are bounded to `STREAM_CACHE_BUDGET_GB`
  (default 20) across HLS and mobile renditions, evicting the least recently
  played entries, and transcodes and uploads are refused when the data
  volume has less than `MIN_FREE_DISK_GB` (default 2) free. Lower both on a
  small boot SSD.
