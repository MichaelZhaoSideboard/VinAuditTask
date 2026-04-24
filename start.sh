#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
    echo "Shutting down..."
    kill 0
}
trap cleanup EXIT

echo "Starting API server..."
cd "$ROOT/api"
uvicorn app.main:app --reload &

echo "Starting web dev server..."
cd "$ROOT/web"
npm run dev &

wait
