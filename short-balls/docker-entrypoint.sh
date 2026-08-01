#!/bin/sh
set -e
mkdir -p /work/inputs /work/reels
exec python3 /usr/local/bin/tennis_reels.py "$@"
