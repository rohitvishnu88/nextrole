#!/usr/bin/env bash
# Production mode for sharing the app through Tailscale Funnel.
# Builds the frontend, then runs both servers on localhost only: the sole way in from
# outside is Funnel -> Next.js (:3000), which forwards /api to FastAPI (:8000).
# Settings come from the environment or from an env file kept outside the repo.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${NEXTROLE_ENV:-$HOME/.config/nextrole/env}"

if [ -f "$ENV_FILE" ]; then
  if [ -n "$(find "$ENV_FILE" -perm -go=r 2>/dev/null)" ]; then
    echo "Warning: $ENV_FILE is readable by other users. Run: chmod 600 \"$ENV_FILE\""
  fi
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

missing=()
for var in ANTHROPIC_API_KEY TAVILY_API_KEY SESSION_SECRET GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET OWNER_EMAIL PUBLIC_BASE_URL; do
  if [ -z "${!var:-}" ]; then
    missing+=("$var")
  fi
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing settings: ${missing[*]}"
  echo "Set them in $ENV_FILE (see README: 'Sharing with friends')."
  exit 1
fi
case "$PUBLIC_BASE_URL" in
  https://*) ;;
  *) echo "PUBLIC_BASE_URL must be the https:// Funnel address, got: $PUBLIC_BASE_URL"; exit 1 ;;
esac
export CORS_ORIGINS="$PUBLIC_BASE_URL"

for port in 8000 3000; do
  pids="$(lsof -ti ":$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "Stopping existing process(es) on port $port: $pids"
    kill $pids 2>/dev/null || true
  fi
done

echo "Building frontend..."
(cd "$ROOT_DIR/web" && npm run build)

cleanup() {
  echo
  echo "Shutting down..."
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
  wait "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd "$ROOT_DIR" && python3 -m uvicorn a2a.server:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
(cd "$ROOT_DIR/web" && npx next start --hostname 127.0.0.1 --port 3000) &
FRONTEND_PID=$!

echo
echo "Running on localhost. Share it with:  tailscale funnel --bg 3000"
echo "Friends open: $PUBLIC_BASE_URL"
echo "Press Ctrl+C to stop."
wait "$BACKEND_PID" "$FRONTEND_PID"
