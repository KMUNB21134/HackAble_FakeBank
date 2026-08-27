#!/usr/bin/env bash
# Builds and runs FakeBank in a Docker container via Colima - a
# lightweight, GUI-free container runtime for macOS. See README's
# "Running in Docker" section for why this matters: it keeps the
# Werkzeug RCE challenge contained to a disposable container instead
# of reaching your real machine.
#
# Installs colima/docker via Homebrew if missing, starts the Colima VM
# if it is not already running, builds the image, and runs it in the
# foreground - Ctrl+C (or `kill` from anywhere) stops the container
# and removes it (--rm), via the same explicit process-group signal
# forwarding run.sh uses on bare metal - a signal aimed at just this
# script's own PID would not otherwise reach `docker run` cleanly.
#
# Colima itself and the built image are left in place between runs -
# rebuilding the VM from scratch every time would take minutes for no
# benefit. Tear those down yourself if you want a full teardown:
#   docker rmi fakebank
#   colima stop && colima delete -f
#   brew uninstall colima docker lima
#
# By default this only publishes to localhost (127.0.0.1). Pass --lan
# to publish on your machine's real network interface instead, making
# it reachable by other devices on your WiFi.
set -uo pipefail
cd "$(dirname "$0")"

BIND="127.0.0.1"
if [[ "${1:-}" == "--lan" ]]; then
    BIND="0.0.0.0"
    echo "Publishing on 0.0.0.0 - reachable by other devices on your network."
fi

if ! command -v colima >/dev/null 2>&1 || ! command -v docker >/dev/null 2>&1; then
    echo "Installing colima and docker via Homebrew..."
    brew install colima docker
fi

if ! colima status >/dev/null 2>&1; then
    echo "Starting Colima (first start can take a few minutes)..."
    colima start
fi

echo "Building the fakebank image..."
docker build -t fakebank . || exit 1

# Job control puts `docker run` in its own process group, so a signal
# aimed at just this script's PID can still be forwarded to it - not
# only a terminal Ctrl+C, which already hits the whole foreground
# group on its own.
set -m

echo "Starting the container on ${BIND}:5005 (Ctrl+C to stop)..."
docker run --rm -p "${BIND}:5005:5005" --name fakebank_run fakebank &
RUN_PID=$!

forward_and_stop() {
    kill -TERM -- "-$RUN_PID" 2>/dev/null
    wait "$RUN_PID" 2>/dev/null
}
trap forward_and_stop INT TERM EXIT

wait "$RUN_PID"
