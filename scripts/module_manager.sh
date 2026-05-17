#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# FOMO — Module Manager
#
# Enable/disable individual intelligence modules and run one-off pipeline
# cycles. See ARCHITECTURE.md §7 for what each module does.
#
# Usage:
#   bash scripts/module_manager.sh status
#   bash scripts/module_manager.sh enable  <module>
#   bash scripts/module_manager.sh disable <module>
#   bash scripts/module_manager.sh run     <module>
#   bash scripts/module_manager.sh replay  <asset> [start YYYY-MM-DD]
#
# Modules: fractal | exchange | sentiment | onchain | metabrain |
#          polymarket | telegram-intel | funnel | growth
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; B='\033[0;34m'; N='\033[0m'
ok(){ echo -e "${G}✓${N} $*"; }
warn(){ echo -e "${Y}⚠${N} $*"; }
err(){ echo -e "${R}✗${N} $*" >&2; }
info(){ echo -e "${B}●${N} $*"; }

APP_ROOT="${APP_ROOT:-/app}"
ENV_FILE="$APP_ROOT/backend/.env"
[ -f "$ENV_FILE" ] || { err "$ENV_FILE missing — run cold_boot.sh first"; exit 1; }
set -a; . "$ENV_FILE"; set +a

ACTION="${1:-status}"
MODULE="${2:-}"

# Maps module name → env flag(s)
mod_flags() {
  case "$1" in
    sentiment)        echo "SENTIMENT_INTAKE_ENABLED SENTIMENT_AGG_ENABLED SENTIMENT_ML_ENABLED" ;;
    onchain)          echo "ONCHAIN_ENABLED" ;;
    telegram-intel)   echo "TELEGRAM_INTEL_ENABLED" ;;
    fractal|exchange|metabrain|polymarket|funnel|growth)  echo "" ;;
    *) return 1 ;;
  esac
}

# Maps module name → one-off command
mod_cmd() {
  case "$1" in
    fractal)        echo "python3 -c 'import sys; sys.path.insert(0,\"/app/backend\"); from fractal_forecast.pipeline import run_all_pipelines; print(run_all_pipelines())'" ;;
    exchange)       echo "python3 /app/backend/scripts/run_signal_engine.py" ;;
    sentiment)      echo "python3 /app/backend/scripts/run_twitter_pipeline.py && python3 /app/backend/scripts/run_rss_pipeline.py" ;;
    onchain)        echo "python3 -c 'import asyncio,sys; sys.path.insert(0,\"/app/backend\"); from services.signals_service import refresh_onchain; asyncio.run(refresh_onchain())' 2>/dev/null || echo onchain module hook missing" ;;
    metabrain)      echo "python3 -c 'import asyncio,sys; sys.path.insert(0,\"/app/backend\"); from services.meta_brain_service import refresh_all; asyncio.run(refresh_all())' 2>/dev/null || echo metabrain module hook missing" ;;
    polymarket)     echo "DB_NAME=\${DB_NAME:-fomo_mobile} MONGO_URL=\${MONGO_URL:-mongodb://localhost:27017} python3 /app/backend/scripts/run_polymarket_once.py" ;;
    telegram-intel) echo "python3 -c 'import sys; sys.path.insert(0,\"/app/backend\"); from telegram_intel.smoke_test import run_smoke; run_smoke()'" ;;
    funnel)         echo "python3 /app/backend/scripts/funnel_report.py" ;;
    growth)         echo "echo '── Funnel (24h) ──'; curl -s 'http://localhost:8001/api/mobile/analytics/summary?hours=24' | python3 -m json.tool; echo; echo '── Growth Metrics (48h) ──'; curl -s 'http://localhost:8001/api/mobile/analytics/growth-metrics?hours=48' | python3 -m json.tool" ;;
    *) return 1 ;;
  esac
}

# ── status: show every module + state ────────────────────────────────
if [ "$ACTION" = status ]; then
  printf "\n%-18s | %s\n" "MODULE" "STATE"
  printf "%s\n" "-------------------+-----------------------------------"
  for m in fractal exchange sentiment onchain metabrain polymarket telegram-intel funnel growth; do
    flags=$(mod_flags "$m")
    if [ -z "$flags" ]; then
      printf "%-18s | %s\n" "$m" "always-on (scheduler)"
    else
      state=""
      for f in $flags; do
        val="${!f:-<unset>}"
        state+="$f=$val  "
      done
      printf "%-18s | %s\n" "$m" "$state"
    fi
  done
  echo ""
  info "Backend / Expo services:"
  if command -v supervisorctl >/dev/null 2>&1; then
    sudo supervisorctl status backend expo mongodb 2>/dev/null | sed 's/^/    /' || true
  fi
  exit 0
fi

# All other actions need a module
[ -n "$MODULE" ] || { err "usage: $0 {enable|disable|run|replay} <module> [...]"; exit 1; }

flip_flags() {
  local val="$1"; shift
  for f in "$@"; do
    if grep -qE "^${f}=" "$ENV_FILE"; then
      sed -i -E "s|^${f}=.*|${f}=${val}|" "$ENV_FILE"
    else
      echo "${f}=${val}" >> "$ENV_FILE"
    fi
    ok "$f = $val"
  done
}

case "$ACTION" in
  enable)
    flags=$(mod_flags "$MODULE") || { err "Unknown module: $MODULE"; exit 1; }
    if [ -z "$flags" ]; then warn "$MODULE is always-on; no flag to flip"; exit 0; fi
    flip_flags "true" $flags
    info "Restart backend for env to take effect: sudo supervisorctl restart backend"
    ;;

  disable)
    flags=$(mod_flags "$MODULE") || { err "Unknown module: $MODULE"; exit 1; }
    if [ -z "$flags" ]; then warn "$MODULE is always-on; cannot disable without code change"; exit 0; fi
    flip_flags "false" $flags
    info "Restart backend for env to take effect: sudo supervisorctl restart backend"
    ;;

  run)
    cmd=$(mod_cmd "$MODULE") || { err "Unknown module: $MODULE"; exit 1; }
    info "Running one-off cycle: $MODULE"
    echo "    \$ $cmd"
    eval "$cmd"
    ok "Done"
    ;;

  replay)
    ASSET="${MODULE}"; START="${3:-2024-01-01}"
    BASE="${APP_URL:-http://localhost:8001}"
    info "Replaying forecasts: asset=$ASSET start=$START"
    curl -s -X POST "${BASE}/api/system/bootstrap/replay?start=${START}&asset=${ASSET}" \
         -w "\nHTTP %{http_code}\n" | head -c 2000
    echo ""
    ok "Replay issued"
    ;;

  *)
    err "Unknown action: $ACTION"
    exit 1
    ;;
esac
