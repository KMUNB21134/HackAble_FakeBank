#!/usr/bin/env bash
# Starts new_api.py (the second automation API - see CLAUDE.md/README) in
# the background, then runs app.py in the foreground as the container's
# main process (PID 1), so `docker stop` / Ctrl+C via colima.sh's signal
# forwarding still cleanly stops everything, and `docker run --rm` still
# wipes fakebank.db/.rce_flag on exit the same way it always did.
set -e

uvicorn new_api:app --host 127.0.0.1 --port 8000 &

exec python app.py
