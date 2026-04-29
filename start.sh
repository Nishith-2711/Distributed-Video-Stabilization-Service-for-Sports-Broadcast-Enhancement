#!/bin/bash
set -e

echo "Starting Redis..."
redis-server --daemonize yes

echo "Waiting for Redis to start..."
sleep 2

echo "Starting RQ Worker in background..."
rq worker video-processing --url redis://localhost:6379 &
WORKER_PID=$!

echo "Starting FastAPI..."
exec uvicorn api.main:app --host 0.0.0.0 --port 7860
