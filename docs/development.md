# Local development

[← Back to the README](../README.md)

The [deploy guides](deploy/) run the published containers. To run from source, you need
both services up at once — the web app talks to the API over HTTP, so a web server on
its own just shows "Could not reach the server".

**Both at once (recommended):**

```bash
./scripts/dev.sh
# or, equivalently:
cd frontend && npm run dev:all
```

That starts the API on `:8000` and the web app on `:5173`, prefixes their logs so you
can tell them apart, and stops both on Ctrl+C. Override ports with
`API_PORT=8010 WEB_PORT=5180 ./scripts/dev.sh`.

**Or separately, in two terminals:**

```bash
# Terminal 1 — API
cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — web app
cd frontend && npm run dev
```

Then open `http://localhost:5173`. Interactive API docs are at `http://localhost:8000/docs`.

## First-time setup

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd frontend && npm install
```

`backend/.env` controls the API. `MUSIC_LIBRARY_PATH` must point at a directory that
actually exists, or scanning finds nothing and playback returns 404 for every track —
browsing and insights still work off the indexed database.

## Checks

```bash
cd frontend
npm run test    # unit + integration suite
npm run lint
npm run build
```

## How a file becomes a track

`backend/app/services/track_resolution.py` is the one place that decides a
track's title, artist, album and credits, for new imports and re-reads alike.
The order of trust, for every field: the tag, then the file's name, then its
folders.

- Tags are read through mutagen's easy interface, so MP3, FLAC, M4A, OGG, Opus
  and WAV all answer to the same keys. Multi-valued artist and genre tags are
  joined with `; ` and split again by the normaliser. A missing tag is `None`,
  never the filename.
- The name parser (`filename_metadata.py`) finds the track number by what it
  is, wherever it sits: `Artist - Album - 07 - Title`, `Artist - 07 - Title`,
  `07 - Title`, `07 Title`, `1-07 Title`. What is after the number is the
  title, dashes included.
- The folder parser gives `Artist/Album (Year)/[Disc 2]/file` its artist and
  album when nothing else does. The library root and generic folder names
  (`Music`, `Lossless`) name nothing.

To see how one file would be imported:

```bash
cd backend && .venv/bin/python -m app.scripts.debug_metadata_resolution "/music/Artist/Album/07 - Title.flac"
```

Rows the old reader misread (an artist that is a bare number, no artist at
all, an `.m4a` with no tags recorded) are re-read by the scanner on its next
walk. To do the whole library at once instead:

```bash
cd backend && .venv/bin/python -m app.scripts.backfill_filename_metadata
```

It re-reads only those rows from their files; every other row is re-resolved
from the tags it already stored. Genres are left alone.

## Track durations

Durations are read from file tags during a scan. To fill them in for tracks that were
indexed before that existed:

```bash
cd backend && .venv/bin/python -m app.scripts.backfill_durations
```

It needs the music volume mounted, and skips files it cannot find.
