#!/usr/bin/env bash
# Export the built image for offline use. Restore with: docker load < dist/<file>
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
TAG="${IMETRO_TAG:-latest}"
docker save "imetro-sandbox:${TAG}" | gzip > "dist/imetro-sandbox-${TAG}.tar.gz"
echo "Wrote dist/imetro-sandbox-${TAG}.tar.gz"
