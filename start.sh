#!/bin/bash

# Resume Builder — start both servers
# Usage: ./start.sh

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌ python3 not found. Install Python 3.9+ and try again."
  exit 1
fi

# Check Node
if ! command -v node &>/dev/null; then
  echo "❌ node not found. Install Node.js 18+ and try again."
  exit 1
fi

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "❌ ANTHROPIC_API_KEY is not set. Export it and try again."
  exit 1
fi

echo "Starting Resume Builder..."
echo "  Backend → http://localhost:8000"
echo "  Frontend → http://localhost:3000"
echo "  Press Ctrl+C to stop both."
echo ""

# Trap Ctrl+C and kill both processes
trap 'kill 0' SIGINT SIGTERM

python3 -m uvicorn a2a.server:app --port 8000 &
cd web && npm run dev &

wait
