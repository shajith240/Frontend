#!/usr/bin/env bash
# Start both the FastAPI backend (port 8000) and Streamlit frontend (port 8501).
# Usage: ./run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Module 1 — Patient Demographics & Visit History"
echo "========================================================="
echo ""

# Start FastAPI in the background
echo "[1/2] Starting FastAPI server on http://localhost:8000 ..."
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!

# Give FastAPI a moment to bind the port
sleep 2

# Start Streamlit in the foreground
echo "[2/2] Starting Streamlit app on http://localhost:8501 ..."
echo ""
echo "  API docs:  http://localhost:8000/docs"
echo "  Frontend:  http://localhost:8501"
echo ""

streamlit run app.py --server.port 8501

# When Streamlit exits, clean up FastAPI
kill $FASTAPI_PID 2>/dev/null || true
