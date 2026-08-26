#!/usr/bin/env bash
# Runs the app, then removes everything it generates at runtime once it
# stops - fakebank.db and its SQLite WAL sidecar files, plus the RCE
# challenge's flag file. Lives outside app.py on purpose: debug=True's
# reloader restarts the Python process on every file save, and cleanup
# logic inside app.py itself would fire on every one of those restarts
# too, wiping the seeded database mid-session.
#
# Run this directly in a terminal (./run.sh), not backgrounded - a
# background job has SIGINT permanently ignored by shell convention
# (so a terminal's Ctrl+C does not kill background jobs by accident),
# and that disposition cannot be undone from inside the script. Run in
# the foreground, Ctrl+C reaches it normally; `kill <pid>` (SIGTERM)
# from anywhere - a process manager, another terminal - is handled
# explicitly below either way.
set -uo pipefail
cd "$(dirname "$0")"

# Job control puts the python process (and the reloader child it spawns)
# in its own process group, so the signal this script receives can be
# forwarded to every process underneath it, not just the immediate
# child.
set -m

cleanup() {
    rm -f fakebank.db fakebank.db-journal fakebank.db-wal fakebank.db-shm .rce_flag
}

.venv/bin/python app.py &
APP_PID=$!

forward_and_cleanup() {
    kill -TERM -- "-$APP_PID" 2>/dev/null
    wait "$APP_PID" 2>/dev/null
    cleanup
}
trap forward_and_cleanup INT TERM EXIT

wait "$APP_PID"
