#!/usr/bin/env bash
# Start backend and frontend (Unix shells)
# Usage: ./start-dev.sh from project root

set -e
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
elif [ -f ./.venv/bin/activate ]; then
  source ./.venv/bin/activate
else
  echo "No virtualenv found in .venv or .venv. Create and activate it first."
fi

# Start backend in background
nohup uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!

echo "Started backend (pid=$BACKEND_PID)"

# Start frontend (blocking)
cd ui
npm run dev
