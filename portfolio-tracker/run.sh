#!/bin/bash
export PATH="/c/Program Files/nodejs:$PATH"
export PATH="/c/Users/pardh/AppData/Local/Programs/Python/Python312:/c/Users/pardh/AppData/Local/Programs/Python/Python312/Scripts:$PATH"

echo "Starting portfolio-tracker..."

(cd backend && uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload) &
(cd frontend && npm start) &
wait
