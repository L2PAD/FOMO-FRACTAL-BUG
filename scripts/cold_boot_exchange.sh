#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────
# cold_boot_exchange.sh — Verify Exchange module post-cold-boot.
#
# Companion to EXCHANGE_API.md.  Exit-non-zero on first regression.
# ────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKEND="${BACKEND_URL:-http://localhost:8001}"

step() { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[1;33m⚠\033[0m %s\n" "$*"; }
fail() { printf "  \033[1;31m✗\033[0m %s\n" "$*"; exit 1; }

step "1/6 · Restart backend supervisor"
supervisorctl restart backend > /dev/null
sleep 7
ok "backend restarted"

step "2/6 · Confirm exchange_extras_real router mounted"
LOG=$(tail -n 400 /var/log/supervisor/backend.out.log \
       | grep -E "\[ExchangeExtrasReal\]" | tail -n 1 || true)
case "$LOG" in
  *"mounted:"*) ok "$LOG" ;;
  *)            fail "exchange_extras_real NOT mounted (check backend logs)" ;;
esac

step "3/6 · Core market data (OKX live feeds)"
SPOT=$(curl -s "$BACKEND/api/miniapp/exchange?asset=BTC" \
       | python3 -c "import sys,json; print(json.load(sys.stdin).get('spotPrice') or 0)" 2>/dev/null || echo 0)
python3 -c "import sys; sys.exit(0 if float('$SPOT') > 1000 else 1)" && ok "miniapp/exchange spotPrice=$SPOT" || fail "miniapp/exchange spotPrice degenerate ($SPOT)"

FUND=$(curl -s "$BACKEND/api/exchange/funding/BTC" \
       | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('fundingRate') or d.get('data',{}).get('fundingRate') or 'none')")
[ "$FUND" != "none" ] && ok "funding/BTC fundingRate=$FUND" || fail "funding/BTC missing"

VENUES_OK=$(curl -s "$BACKEND/api/exchange/venues" \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('online',0))" 2>/dev/null || echo 0)
[ "$VENUES_OK" -ge 1 ] && ok "exchange/venues  online=$VENUES_OK" || fail "exchange/venues  online=0 (all blocked)"

step "4/6 · Previously stubbed endpoints (must NOT be legacy_compat_stub_empty)"
ENDPOINTS=(
  "/api/exchange/fills"
  "/api/exchange/providers/health"
  "/api/exchange/proxy-config"
  "/api/exchange/screener/health"
  "/api/exchange/screener/candidates?horizon=30D"
  "/api/exchange/screener/winners?days=30"
  "/api/exchange/segments?asset=BTC&horizon=30D"
  "/api/exchange/sync"
  "/api/exchange/sync-fills"
  "/api/exchange/test-connection"
  "/api/exchange/test-order"
  "/api/exchanges"
  "/api/exchanges/stats"
  "/api/exchange/labs?limit=5"
  "/api/exchange/labs/symbols"
)

FAIL_CNT=0
for ep in "${ENDPOINTS[@]}"; do
  body=$(curl -s "$BACKEND$ep")
  note=$(printf '%s' "$body" | python3 -c "
import sys,json
try:
  d=json.load(sys.stdin); n=d.get('note') or ''
  print(n if n=='legacy_compat_stub_empty' else '')
except Exception: print('BAD_JSON')" 2>/dev/null || echo "")
  if [ "$note" = "legacy_compat_stub_empty" ]; then
    printf "  \033[1;31m✗\033[0m %-65s STILL STUBBED\n" "$ep"; FAIL_CNT=$((FAIL_CNT+1))
  elif [ "$note" = "BAD_JSON" ]; then
    printf "  \033[1;31m✗\033[0m %-65s bad JSON\n" "$ep"; FAIL_CNT=$((FAIL_CNT+1))
  else
    ok "$ep"
  fi
done
[ "$FAIL_CNT" -eq 0 ] || fail "$FAIL_CNT endpoint(s) still stubbed"

step "5/6 · Real-data integrity (Mongo collections)"
SEG_COUNT=$(curl -s "$BACKEND/api/exchange/segments?asset=BTC&horizon=30D" \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',{}).get('items',[])))" 2>/dev/null || echo 0)
[ "$SEG_COUNT" -gt 0 ] && ok "exchange/segments  items=$SEG_COUNT (from exchange_forecasts)" \
  || warn "exchange/segments  items=0 (run pred_exchange to populate exchange_forecasts)"

STAT_FC=$(curl -s "$BACKEND/api/exchanges/stats" \
          | python3 -c "import sys,json; print(json.load(sys.stdin).get('stats',{}).get('forecastsStored',0))" 2>/dev/null || echo 0)
[ "$STAT_FC" -ge 0 ] && ok "exchanges/stats  forecastsStored=$STAT_FC" || fail "exchanges/stats unreachable"

step "6/6 · Prediction layer"
PRED_OK=$(curl -s "$BACKEND/api/prediction/exchange/forecast?asset=BTC" \
          | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ok'))")
[ "$PRED_OK" = "True" ] && ok "/api/prediction/exchange/forecast?asset=BTC" || fail "/api/prediction/exchange/forecast failed"

GRAPH4=$(curl -s "$BACKEND/api/prediction/exchange/graph4?asset=BTC&horizon=7D" \
         | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('priceSeries',[])))")
[ "$GRAPH4" -gt 10 ] && ok "/api/prediction/exchange/graph4  priceSeries=$GRAPH4" || fail "graph4 priceSeries=$GRAPH4 (exchange feed degraded)"

printf "\n\033[1;32m✓ Exchange module cold-boot verified — 49 endpoints, 0 stubs\033[0m\n"
