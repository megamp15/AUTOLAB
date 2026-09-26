#!/bin/sh
# A virtual display for anything in the editor that opens a window, then the
# image's own entrypoint. exec keeps the same process, so Xvfb stays a child
# of it all the way down to the entrypoint's dumb-init, which reaps it.
set -eu

Xvfb "${DISPLAY}" -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 &

exec "$@"
