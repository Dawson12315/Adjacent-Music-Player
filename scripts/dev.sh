#!/usr/bin/env bash
#
# Start the Adjacent API and web app together.
#
# Both have to be running at once — the web app is useless on its own, and a dead API
# shows up in the browser as "Could not reach the server". This starts both, prefixes
# their output so you can tell them apart, and shuts both down on Ctrl+C.
#
#   ./scripts/dev.sh              # or: cd frontend && npm run dev:all
#
# Ports can be overridden:  API_PORT=8010 WEB_PORT=5180 ./scripts/dev.sh
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

VENV_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
VITE_BIN="$REPO_ROOT/frontend/node_modules/.bin/vite"

BLUE=$'\033[34m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; DIM=$'\033[2m'; RESET=$'\033[0m'

log()  { printf "%s\n" "${DIM}▸${RESET} $*"; }
fail() { printf "%s\n" "${RED}✗${RESET} $*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight

[ -x "$VENV_PYTHON" ] || fail "No Python virtualenv at backend/.venv
  Create one first:
    cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"

if [ ! -x "$VITE_BIN" ]; then
  log "Installing frontend dependencies (first run)…"
  (cd "$REPO_ROOT/frontend" && npm install) || fail "npm install failed"
fi

port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

port_busy "$API_PORT" && fail "Port $API_PORT is already in use.
  Something is already serving the API — stop it, or set API_PORT to another port."
port_busy "$WEB_PORT" && fail "Port $WEB_PORT is already in use.
  Stop the other dev server, or set WEB_PORT to another port."

# ---------------------------------------------------------------- shutdown
#
# Each service is started as a direct background job — not wrapped in a subshell — so
# $! is the real process and signalling it actually reaches the server. Output is
# prefixed through process substitution, which keeps that true.
#
# uvicorn --reload runs a supervisor that forks the app process; it forwards SIGTERM to
# its child. Killing descendants afterwards covers anything that ignores it.

API_PID=""
WEB_PID=""

# The `>(awk …)` output filters are bash subshells and they inherit this script's traps.
# On Ctrl+C the whole foreground process group is signalled, so every one of them would
# otherwise run cleanup and print the shutdown notice too.
#
# `mkdir` is atomic, so the first caller into cleanup wins and the rest bow out. This is
# deliberately not $BASHPID: macOS ships bash 3.2, which does not have it.
CLEANUP_LOCK="${TMPDIR:-/tmp}/adjacent-dev-$$.lock"

stop_tree() {
  local pid="$1"
  [ -n "$pid" ] || return 0
  kill -TERM "$pid" 2>/dev/null
  pkill -TERM -P "$pid" 2>/dev/null
}

kill_tree() {
  local pid="$1"
  [ -n "$pid" ] || return 0
  pkill -KILL -P "$pid" 2>/dev/null
  kill -KILL "$pid" 2>/dev/null
}

cleanup() {
  # Only the first caller tears things down; inherited trap copies bow out.
  mkdir "$CLEANUP_LOCK" 2>/dev/null || exit 0

  trap - INT TERM EXIT
  printf "\n%s\n" "${DIM}▸${RESET} Shutting down…"

  stop_tree "$API_PID"
  stop_tree "$WEB_PID"

  # Give them a second to exit cleanly, then insist.
  for _ in $(seq 1 20); do
    if ! kill -0 "$API_PID" 2>/dev/null && ! kill -0 "$WEB_PID" 2>/dev/null; then
      break
    fi
    sleep 0.25
  done

  kill_tree "$API_PID"
  kill_tree "$WEB_PID"

  rmdir "$CLEANUP_LOCK" 2>/dev/null
  wait 2>/dev/null
  exit 0
}

trap cleanup INT TERM EXIT

# ---------------------------------------------------------------- start

log "Starting API on :$API_PORT"
cd "$REPO_ROOT/backend" || fail "Missing backend/"
"$VENV_PYTHON" -m uvicorn app.main:app --reload --port "$API_PORT" \
  > >(awk -v p="${BLUE}[api]${RESET} " '{ print p $0; fflush() }') 2>&1 &
API_PID=$!

log "Starting web app on :$WEB_PORT"
cd "$REPO_ROOT/frontend" || fail "Missing frontend/"
"$VITE_BIN" --port "$WEB_PORT" --strictPort \
  > >(awk -v p="${YELLOW}[web]${RESET} " '{ print p $0; fflush() }') 2>&1 &
WEB_PID=$!

cd "$REPO_ROOT"

# ---------------------------------------------------------------- ready

ready=false
for _ in $(seq 1 90); do
  # If either died on startup, stop waiting and let the output explain why.
  if ! kill -0 "$API_PID" 2>/dev/null || ! kill -0 "$WEB_PID" 2>/dev/null; then
    break
  fi

  if curl -sf -m 1 "http://localhost:$API_PORT/api/health" >/dev/null 2>&1 &&
     curl -sf -m 1 "http://localhost:$WEB_PORT/" >/dev/null 2>&1; then
    ready=true
    break
  fi

  sleep 0.5
done

if [ "$ready" = true ]; then
  printf "\n  %s\n" "Adjacent is running:"
  printf "    web  →  http://localhost:%s\n" "$WEB_PORT"
  printf "    api  →  http://localhost:%s/docs\n\n" "$API_PORT"
  printf "  %s\n\n" "${DIM}Ctrl+C stops both.${RESET}"
else
  printf "\n%s\n\n" "${RED}✗${RESET} One of the services did not come up — see the log above."
fi

wait
