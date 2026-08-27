#!/usr/bin/env bash
# Builds and runs FakeBank in a Docker container on Linux, where
# Docker runs natively - no VM layer needed here, unlike colima.sh on
# macOS (Linux already has the kernel features containers need; Colima
# exists specifically to work around macOS not having those). See
# README's "Running in Docker" section for why containing this app
# matters: the Werkzeug RCE challenge is genuine, and running it in a
# container keeps that confined to a disposable container instead of
# your real machine.
#
# Installs Docker via apt if missing (Debian/Ubuntu/Raspberry Pi OS -
# see the error message below for other distros), then builds the
# image and runs it in the foreground - Ctrl+C (or `kill` from
# anywhere) stops and removes the container.
#
# The image and Docker itself are left in place between runs. For a
# full teardown:
#   docker rmi fakebank
#   sudo apt remove docker.io
#
# By default this only publishes to localhost (127.0.0.1). Pass --lan
# to publish on the real network interface instead, making it
# reachable by other devices on your network.
set -uo pipefail
cd "$(dirname "$0")"

BIND="127.0.0.1"
if [[ "${1:-}" == "--lan" ]]; then
    BIND="0.0.0.0"
    echo "Publishing on 0.0.0.0 - reachable by other devices on your network."
fi

if ! command -v docker >/dev/null 2>&1; then
    if command -v apt >/dev/null 2>&1; then
        echo "Installing docker via apt (needs sudo)..."
        sudo apt update && sudo apt install -y docker.io
    else
        echo "docker is not installed, and this script only knows how to" >&2
        echo "install it via apt (Debian/Ubuntu/Raspberry Pi OS). Install" >&2
        echo "Docker yourself for your distro, then re-run this script:" >&2
        echo "  https://docs.docker.com/engine/install/" >&2
        exit 1
    fi
fi

if ! docker info >/dev/null 2>&1; then
    echo "Cannot talk to the Docker daemon. Either it is not running yet" >&2
    echo "(try: sudo systemctl start docker), or your user is not in the" >&2
    echo "docker group yet:" >&2
    echo "  sudo usermod -aG docker \$USER" >&2
    echo "then log out and back in - group membership does not apply to" >&2
    echo "an already-running shell - and re-run this script." >&2
    exit 1
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
