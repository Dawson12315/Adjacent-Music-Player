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
- **Cache size.** The transcode caches are bounded to `STREAM_CACHE_BUDGET_GB`
  (default 20) across HLS and mobile renditions, evicting the least recently
  played entries, and transcodes and uploads are refused when the data
  volume has less than `MIN_FREE_DISK_GB` (default 2) free. Lower both on a
  small boot SSD.
