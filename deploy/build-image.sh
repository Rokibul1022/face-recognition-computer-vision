#!/usr/bin/env bash
# Build + push the seeded backend image for Render.
# Requires: Docker (Docker Desktop on Windows), docker login <registry> done.
#
# Usage:
#   ./deploy/build-image.sh ghcr.io/your-user/ident-backend:seed
#   ./deploy/build-image.sh your-user/ident-backend:seed   (Docker Hub)
#
# Build context is the repo root; the Dockerfile bakes your stored data
# (backend/data, gallery, agent.db, memory) + model weights into the image,
# so the deployed app starts with your exact seeded state.
set -euo pipefail

IMAGE="${1:?usage: build-image.sh <image-name:tag>}"

echo "==> Building ${IMAGE} (this bakes data/ + models/; ~700MB, may take a few minutes)"
docker build \
  --file backend/Dockerfile.prod \
  -t "${IMAGE}" \
  .

echo "==> Pushing ${IMAGE}"
docker push "${IMAGE}"

echo
echo "Done. In Render dashboard: Web Service -> Deploy from container image."
echo "Or paste backend/render.yaml (edit the image name + OPENAI_API_KEY)."