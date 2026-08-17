#!/usr/bin/env sh
# Production entrypoint.
#
# Two deployment modes:
#   A) Baked seed (default, works on Render free tier):
#        FR_DATA_DIR/GALLERY/DB already point at the baked /srv/seed copy.
#        No disk needed; new enrollments/events live for the container's
#        lifetime only.
#   B) Persistent disk (Render paid): set FR_DATA_DIR=...=/var/data and
#        FR_COPY_SEED=1. On first boot we copy the baked seed into the empty
#        disk, then everything after that is persistent across restarts.
set -e

if [ -n "$FR_COPY_SEED" ]; then
  if [ -d "$FR_DATA_DIR" ] && [ -z "$(ls -A "$FR_DATA_DIR" 2>/dev/null)" ]; then
    echo "[entrypoint] seeding $FR_DATA_DIR from /srv/seed ..."
    cp -rn /srv/seed/. "$FR_DATA_DIR"/
  else
    echo "[entrypoint] FR_COPY_SEED set but $FR_DATA_DIR is not empty; skipping seed copy."
  fi
fi

echo "[entrypoint] starting uvicorn on 0.0.0.0:${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"