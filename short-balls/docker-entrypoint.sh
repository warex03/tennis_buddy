#!/bin/sh
set -e
HOST_UID="${HOST_UID:-1000}"
HOST_GID="${HOST_GID:-1000}"
mkdir -p /work/inputs /work/reels
# Docker may have created these bind mounts as root; reclaim for the host user.
chown -R "$HOST_UID:$HOST_GID" /work/inputs /work/reels
exec gosu "$HOST_UID:$HOST_GID" python3 /usr/local/bin/tennis_reels.py "$@"
