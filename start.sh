#!/usr/bin/env bash
# Starts the resume-builder backend (FastAPI, :8000) and frontend (Next.js, :3000).
# Kills anything already bound to those ports first so there's never a stale instance.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti ":$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "Killing existing process(es) on port $port: $pids"
    kill -9 $pids 2>/dev/null || true
  fi
}

kill_port 8000
kill_port 3000

cleanup() {
  echo
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on :8000..."
(cd "$ROOT_DIR" && python3 -m uvicorn a2a.server:app --port 8000 --reload) &
BACKEND_PID=$!

echo "Starting frontend on :3000..."
(cd "$ROOT_DIR/web" && npm run dev) &
FRONTEND_PID=$!

echo
echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"
echo "Press Ctrl+C to stop both."

wait "$BACKEND_PID" "$FRONTEND_PID"
