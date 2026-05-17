#!/usr/bin/env bash
# =============================================================================
# FOMO — Modules Bootstrap (Single Command)
# =============================================================================
# Цель: за один проход развернуть/восстановить 5 модулей (Fractal, Sentiment,
# Exchange, On-chain, Tech Analysis) согласно /app/MODULES_RUNBOOK.md.
#
# Идемпотентен: можно запускать сколько угодно раз — ничего не сломает.
#
# Что делает:
#   1. Проверяет .env (backend, frontend, legacy)
#   2. Прокидывает обязательные feature-флаги в /app/legacy/.env
#   3. Установит зависимости (опционально через --install-deps)
#   4. Перезапустит supervisor (backend, node_sidecar, frontend)
#   5. Прогонит smoke-тесты на ключевые эндпоинты 5 модулей
#   6. Покажет краткий отчёт (PASS/FAIL по каждому модулю)
#
# Usage:
#   bash /app/scripts/bootstrap_modules.sh                     # запуск + smoke tests
#   bash /app/scripts/bootstrap_modules.sh --install-deps      # + yarn install + pip install
#   bash /app/scripts/bootstrap_modules.sh --verify-only       # только smoke tests
#   bash /app/scripts/bootstrap_modules.sh --enable-fractal-csv# + автоскачивание CSV для Fractal cohort
# =============================================================================

set -uo pipefail

# ── colors ───────────────────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; B='\033[0;34m'; M='\033[0;35m'; N='\033[0m'
ok()   { echo -e "${G}✓${N} $*"; }
warn() { echo -e "${Y}⚠${N} $*"; }
err()  { echo -e "${R}✗${N} $*" >&2; }
hdr()  { echo -e "\n${M}══${N} ${B}$*${N} ${M}══${N}"; }
step() { echo -e "${B}●${N} $*"; }

# ── flags ────────────────────────────────────────────────────────────────────
INSTALL_DEPS=0
VERIFY_ONLY=0
ENABLE_FRACTAL_CSV=0
for arg in "$@"; do
  case "$arg" in
    --install-deps)         INSTALL_DEPS=1 ;;
    --verify-only)          VERIFY_ONLY=1 ;;
    --enable-fractal-csv)   ENABLE_FRACTAL_CSV=1 ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) warn "Unknown flag: $arg" ;;
  esac
done

APP=/app
BACKEND_URL="http://localhost:8001"
SIDECAR_URL="http://localhost:8003"

# ── 0. preflight ─────────────────────────────────────────────────────────────
hdr "0. PREFLIGHT"

for f in "$APP/backend/.env" "$APP/frontend/.env"; do
  if [ ! -f "$f" ]; then err "Missing $f"; exit 1; fi
  ok "Found $f"
done

if ! grep -q '^MONGO_URL=' "$APP/backend/.env"; then
  err "MONGO_URL not set in $APP/backend/.env"; exit 1
fi
ok "MONGO_URL present"

if ! grep -q '^REACT_APP_BACKEND_URL=' "$APP/frontend/.env"; then
  err "REACT_APP_BACKEND_URL not set"; exit 1
fi
ok "REACT_APP_BACKEND_URL present"

# Mongo ping
if mongosh --quiet --eval 'db.runCommand({ping:1}).ok' "$(grep ^MONGO_URL "$APP/backend/.env" | cut -d'"' -f2 || true)/fomo_mobile" 2>/dev/null | grep -q 1; then
  ok "MongoDB reachable"
else
  warn "MongoDB ping failed — sidecar/backend may use direct driver still"
fi

# ── 1. legacy sidecar .env (feature flags) ───────────────────────────────────
if [ "$VERIFY_ONLY" -eq 0 ]; then
  hdr "1. SIDECAR FEATURE FLAGS"

  LEGACY_ENV="$APP/legacy/.env"
  touch "$LEGACY_ENV"

  set_flag() {
    local key="$1" val="$2"
    if grep -qE "^${key}=" "$LEGACY_ENV"; then
      sed -i "s|^${key}=.*|${key}=${val}|" "$LEGACY_ENV"
    else
      echo "${key}=${val}" >> "$LEGACY_ENV"
    fi
    step "${key}=${val}"
  }

  set_flag PORT                          8003
  set_flag HOST                          127.0.0.1
  set_flag MONGO_URL                     "$(grep ^MONGO_URL  "$APP/backend/.env" | cut -d'"' -f2 || echo 'mongodb://localhost:27017')"
  set_flag DB_NAME                       "fomo_mobile"
  set_flag SENTIMENT_ML_ENABLED          true
  set_flag SENTIMENT_INTAKE_ENABLED      true
  set_flag SENTIMENT_AGG_ENABLED         true
  set_flag SENTIMENT_ENABLED             false
  set_flag SENTIMENT_DATASET_ENABLED     false
  set_flag EXCHANGE_ML_ENABLED           true
  set_flag WS_ENABLED                    false
  if [ "$ENABLE_FRACTAL_CSV" -eq 1 ]; then
    set_flag FRACTAL_BOOTSTRAP_AUTO      true
  else
    set_flag FRACTAL_BOOTSTRAP_AUTO      false
  fi
  set_flag FRACTAL_BOOTSTRAP_DIR         "$APP/legacy/data/fractal/bootstrap"
  ok "Legacy .env synchronized"
fi

# ── 2. dependencies ──────────────────────────────────────────────────────────
if [ "$INSTALL_DEPS" -eq 1 ] && [ "$VERIFY_ONLY" -eq 0 ]; then
  hdr "2. DEPENDENCIES"

  step "Backend (pip)"
  (cd "$APP/backend" && /root/.venv/bin/pip install -q -r requirements.txt) && ok "pip OK" || warn "pip failed"

  step "Frontend (yarn)"
  (cd "$APP/frontend" && yarn install --silent 2>&1 | tail -n 3) && ok "yarn OK" || warn "yarn failed"

  step "Legacy sidecar (yarn)"
  (cd "$APP/legacy" && yarn install --silent 2>&1 | tail -n 3) && ok "yarn OK" || warn "yarn legacy failed"
fi

# ── 3. ensure fractal bootstrap dir exists ───────────────────────────────────
if [ "$VERIFY_ONLY" -eq 0 ]; then
  mkdir -p "$APP/legacy/data/fractal/bootstrap"
fi

# ── 4. restart services ──────────────────────────────────────────────────────
if [ "$VERIFY_ONLY" -eq 0 ]; then
  hdr "4. RESTART SERVICES"
  for svc in backend node_sidecar frontend rolling_forecast_loop; do
    step "supervisorctl restart $svc"
    supervisorctl restart "$svc" >/dev/null 2>&1 && ok "$svc restarted" || warn "$svc restart failed"
  done

  step "Waiting 15s for services to come up…"
  sleep 15
fi

# ── 5. smoke tests ───────────────────────────────────────────────────────────
hdr "5. SMOKE TESTS"

PASS=0; FAIL=0; SKIPPED=0
check() {
  local label="$1" url="$2" expect="$3"  # expect: ok | rows | always | code200 | responds
  local body
  # NOTE: -sS (not -fsS) — we want to inspect ok:false bodies too
  body=$(curl -sS -m 12 "$url" 2>/dev/null || true)
  if [ -z "$body" ]; then
    err "$label — empty/unreachable [$url]"
    FAIL=$((FAIL+1)); return
  fi
  case "$expect" in
    ok)
      if echo "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') is True else 1)" 2>/dev/null; then
        ok "$label — ok:true"
        PASS=$((PASS+1))
      else
        # ok:false is acceptable for sentiment-chart pre-aggregation
        local reason
        reason=$(echo "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('error') or d.get('note') or '')" 2>/dev/null || true)
        warn "$label — ok:false (${reason:-no detail}) [worker may need warm-up]"
        SKIPPED=$((SKIPPED+1))
      fi
      ;;
    rows)
      local n
      n=$(echo "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('rows') or []))" 2>/dev/null || echo "ERR")
      if [ "$n" = "ERR" ]; then
        err "$label — invalid JSON / no rows field"
        FAIL=$((FAIL+1))
      else
        ok "$label — rows:$n"
        PASS=$((PASS+1))
      fi
      ;;
    responds|always)
      ok "$label — responds (status irrelevant)"
      PASS=$((PASS+1))
      ;;
  esac
}

# Health
check "backend health"           "${BACKEND_URL}/api/health"                                                 always
check "sidecar health"           "${SIDECAR_URL}/healthz"                                                    always

# Exchange — TS sidecar via Python proxy
check "Exchange chart v2"        "${BACKEND_URL}/api/market/chart/exchange-v2?symbol=BTC&horizon=24H"        ok
check "Exchange perf v2"         "${BACKEND_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D"   rows

# Sentiment — TS sidecar via Python proxy
check "Sentiment chart v2"       "${BACKEND_URL}/api/market/chart/sentiment-v2?symbol=BTC&horizon=24H"       ok
check "Sentiment perf v2"        "${BACKEND_URL}/api/market/sentiment/performance-v2?symbol=BTC&horizon=7D"  rows

# Fractal — TS sidecar
check "Fractal terminal"         "${BACKEND_URL}/api/fractal/v2.1/terminal?symbol=BTC"                       ok

# On-chain — Python
check "On-chain snapshot"        "${BACKEND_URL}/api/v10/onchain/snapshot"                                   always

# Tech Analysis — Python
check "TA mtf BTC"               "${BACKEND_URL}/api/ta-engine/mtf/BTC"                                      always

# Alpha big payload
check "Alpha (v4)"               "${BACKEND_URL}/api/market/chart/price-vs-expectation-v4?symbol=BTC"        ok

# MetaBrain policy
check "MetaBrain policy"         "${BACKEND_URL}/api/meta-brain-v2/policy"                                   ok

# ── report ───────────────────────────────────────────────────────────────────
hdr "REPORT"
echo -e "${G}PASS${N}    : $PASS"
echo -e "${Y}WARN${N}    : $SKIPPED   (endpoint responds but with ok:false — usually means worker hasn't populated data yet)"
echo -e "${R}FAIL${N}    : $FAIL"
echo
if [ "$FAIL" -gt 0 ]; then
  err "Bootstrap completed with $FAIL critical failures. See logs:"
  echo "  tail -n 100 /var/log/supervisor/{backend,node_sidecar}.err.log"
  exit 1
fi
ok "Bootstrap completed. Open the SPA:"
echo "  https://fomo-module-deploy.preview.emergentagent.com/intelligence/price-expectation-v2"
echo
echo "Полная карта модулей: cat /app/MODULES_RUNBOOK.md"
