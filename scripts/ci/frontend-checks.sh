#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../frontend"

if [[ ! -f package-lock.json ]]; then
  echo "ERROR: frontend/package-lock.json is required for reproducible CI." >&2
  echo "Run the manual 'Bootstrap Frontend Lockfile' workflow once, download/commit the lockfile, then re-run CI." >&2
  exit 2
fi

npm ci
npm run check:b63
npm run check:b64
npm run check:b65
npm run check:b66
npm run check:b67
npm run check:b68
npm run check:c1
npm run check:c2
npm run check:c3
npm run check:d1
npm run check:d2
npm run check:d3
npm run typecheck
npm run lint
npm run build
