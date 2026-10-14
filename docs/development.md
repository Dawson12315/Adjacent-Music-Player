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

## Track durations

Durations are read from file tags during a scan. To fill them in for tracks that were
indexed before that existed:

```bash
cd backend && .venv/bin/python -m app.scripts.backfill_durations
```

It needs the music volume mounted, and skips files it cannot find.
