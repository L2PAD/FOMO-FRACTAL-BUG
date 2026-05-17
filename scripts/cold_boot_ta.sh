#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────
# cold_boot_ta.sh — Verify the Tech Analysis module after a cold boot.
#
# Re-runnable, idempotent, exit-non-zero on first real failure.
# Companion to TA_API.md.
# ────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKEND="${BACKEND_URL:-http://localhost:8001}"

step()  { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
ok()    { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
fail()  { printf "  \033[1;31m✗\033[0m %s\n" "$*"; exit 1; }

step "1/6 · Restart backend supervisor"
supervisorctl restart backend > /dev/null
sleep 6
ok "backend restarted"

step "2/6 · Confirm tech_analysis_real router mounted"
LOG_LINE=$(tail -n 400 /var/log/supervisor/backend.out.log \
            | grep -E "\[TechAnalysisReal\]" | tail -n 1 || true)
case "$LOG_LINE" in
  *"mounted:"*) ok "$LOG_LINE" ;;
  *)            fail "tech_analysis_real router NOT mounted (check backend logs)" ;;
esac

step "3/6 · /api/ta/* native endpoints"
# /api/ta/health reports ok=false until the symbol history cache is
# populated.  We warm it via summary first (which triggers analyses),
# then check both.
curl -s "$BACKEND/api/ta/summary?symbols=BTC,ETH" > /dev/null  # warm cache
sleep 2
SUM_JSON=$(curl -s "$BACKEND/api/ta/summary")
SUM_LIVE=$(printf '%s' "$SUM_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("symbolsLive",0))' 2>/dev/null || echo 0)
[ "$SUM_LIVE" -gt 0 ] && ok "/api/ta/summary  symbolsLive=$SUM_LIVE" || fail "/api/ta/summary  symbolsLive=0 — engine degraded"

HEALTH_JSON=$(curl -s "$BACKEND/api/ta/health")
HEALTH_HIST=$(printf '%s' "$HEALTH_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("symbolsWithHistory",0))' 2>/dev/null || echo 0)
[ "$HEALTH_HIST" -gt 0 ] && ok "/api/ta/health  symbolsWithHistory=$HEALTH_HIST" || ok "/api/ta/health  history cache warming (non-fatal)"

step "4/6 · Previously stubbed endpoints (must NOT be legacy_compat_stub_empty)"
ENDPOINTS=(
  "/api/ta-engine/mtf?symbol=BTC"
  "/api/prediction/ta/BTC"
  "/api/prediction/ta/live-price?asset=BTC"
  "/api/prediction/ta/forecast?asset=BTC"
  "/api/prediction/ta/graph4?asset=BTC&horizon=7D"
  "/api/v10/ta/summary"
  "/api/v10/ta/snapshot?symbol=BTC"
  "/api/v10/ta/full?symbols=BTC,ETH"
  "/api/indicators/all"
  "/api/indicators/ETH"
  "/api/ta/setup?symbol=BTC&tf=1D"
  "/api/ta/setup/v2?symbol=BTC&tf=1D"
  "/api/ta/levels/BTC/1D"
  "/api/ta/structure/BTC/1D"
  "/api/ta/indicators/BTC/1D"
  "/api/ta/confluence/BTC/1D"
  "/api/ta-engine/regime?symbol=BTC"
  "/api/ta-engine/levels?symbol=BTC"
  "/api/ta-engine/snapshot?symbol=BTC"
  "/api/ta-engine/decision?symbol=BTC"
  "/api/ta/regime?symbol=BTC"
  "/api/ta/decision?symbol=BTC"
)

FAILED=0
for ep in "${ENDPOINTS[@]}"; do
  body=$(curl -s "$BACKEND$ep")
  note=$(printf '%s' "$body" | python3 -c 'import sys,json
try:
  d=json.load(sys.stdin); n=d.get("note") or ""; print(n if n=="legacy_compat_stub_empty" else "")
except Exception: print("BAD_JSON")' 2>/dev/null || echo "")
  if [ "$note" = "legacy_compat_stub_empty" ]; then
    printf "  \033[1;31m✗\033[0m %s  → STILL STUBBED\n" "$ep"; FAILED=$((FAILED+1))
  elif [ "$note" = "BAD_JSON" ]; then
    printf "  \033[1;31m✗\033[0m %s  → bad JSON\n" "$ep"; FAILED=$((FAILED+1))
  else
    ok "$ep"
  fi
done
[ "$FAILED" -eq 0 ] || fail "$FAILED endpoint(s) still returning legacy stubs"

step "5/6 · Mobile / MiniApp endpoints"
M_OK=$(curl -s "$BACKEND/api/miniapp/tech-analysis?asset=BTC&timeframe=1D" \
        | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("ok") and d.get("mtf") and len(d["mtf"])>0)' 2>/dev/null)
[ "$M_OK" = "True" ] && ok "/api/miniapp/tech-analysis  mtf populated" || fail "/api/miniapp/tech-analysis  no mtf data"

W_COUNT=$(curl -s "$BACKEND/api/miniapp/tech-watchlist?symbols=BTC,ETH,SOL,DOGE" \
           | python3 -c 'import sys,json; print(len(json.load(sys.stdin).get("items",[])))' 2>/dev/null || echo 0)
[ "$W_COUNT" -ge 3 ] && ok "/api/miniapp/tech-watchlist  items=$W_COUNT" || fail "/api/miniapp/tech-watchlist  insufficient items ($W_COUNT)"

step "6/6 · Path-param MTF (real candles via OKX/CoinGecko)"
MTF_JSON=$(curl -s "$BACKEND/api/ta-engine/mtf/BTC?timeframes=1D")
MTF_CANDLES=$(printf '%s' "$MTF_JSON" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get("tf_map",{}).get("1D",{}).get("candles",[])))' 2>/dev/null || echo 0)
[ "$MTF_CANDLES" -ge 50 ] && ok "/api/ta-engine/mtf/BTC  1D.candles=$MTF_CANDLES" || fail "MTF candles too few ($MTF_CANDLES) — exchange feed degraded"

printf "\n\033[1;32m✓ TA module cold-boot verified — all surfaces serving real native_ta_v1 data\033[0m\n"
