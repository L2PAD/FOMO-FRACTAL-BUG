#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# FOMO frontend launcher
#
# Builds static Expo Web export and serves it on $PORT (default 3000)
# via `serve`. Public-URL redirects are configured in serve.json:
#   /admin*    → /api/panel/admin   (canonical FOMO Admin Console)
#   /operator* → /api/panel/admin   (operator surface consolidated)
#
# Rebuild trigger: delete `dist/.fomo-built` or `rm -rf dist`.
# ─────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

PORT="${PORT:-3000}"
HOST="${HOST:-0.0.0.0}"

export PATH="$(pwd)/node_modules/.bin:$PATH"

BUILD_MARKER="dist/.fomo-built"
NEED_BUILD=0
if [ ! -d dist ] || [ ! -f "$BUILD_MARKER" ]; then
  NEED_BUILD=1
fi
# Also rebuild if serve.json was changed AFTER the marker
if [ -f serve.json ] && [ -f "$BUILD_MARKER" ] && [ serve.json -nt "$BUILD_MARKER" ]; then
  NEED_BUILD=1
fi

if [ "$NEED_BUILD" = "1" ]; then
  echo "[FOMO Frontend] Building static web export…"
  rm -rf dist
  expo export --platform web --output-dir dist
  touch "$BUILD_MARKER"
  echo "[FOMO Frontend] Static export complete → dist/"
else
  echo "[FOMO Frontend] Reusing existing dist/"
fi

# Mirror serve.json into dist/ so `serve` picks it up regardless of cwd.
if [ -f serve.json ]; then
  cp serve.json dist/serve.json
fi

# Strip orphan static surfaces from the built artifact so the public URL
# never accidentally exposes the "FOMO Operations" compatibility fallback.
# (Native Expo / Telegram MiniApp / canonical admin are untouched.)
for orphan_dir in admin operator; do
  if [ -d "dist/$orphan_dir" ]; then
    rm -rf "dist/$orphan_dir"
    echo "[FOMO Frontend] Stripped dist/$orphan_dir/ (served via /api/panel/admin)"
  fi
done

echo "[FOMO Frontend] Serving dist/ on ${HOST}:${PORT}"
exec serve dist -l "tcp://${HOST}:${PORT}" -s --no-clipboard --no-port-switching -c serve.json
