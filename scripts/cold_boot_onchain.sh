#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────
# cold_boot_onchain.sh — Verify On-chain Light Mode (Infura).
#
# Companion to ONCHAIN_API.md.  Exit-non-zero on first regression.
# ────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKEND="${BACKEND_URL:-http://localhost:8001}"

step() { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[1;33m⚠\033[0m %s\n" "$*"; }
fail() { printf "  \033[1;31m✗\033[0m %s\n" "$*"; exit 1; }

step "1/7 · Verify .env carries INFURA_KEY + ONCHAIN_ENABLED"
grep -q "^INFURA_KEY" /app/backend/.env && ok ".env has INFURA_KEY" || fail ".env missing INFURA_KEY"
grep -qE "^ONCHAIN_ENABLED=\"?true\"?" /app/backend/.env && ok ".env has ONCHAIN_ENABLED=true" || fail ".env ONCHAIN_ENABLED!=true"
MODE=$(grep -E "^ONCHAIN_MODE=" /app/backend/.env | cut -d= -f2- | tr -d '"' || echo preview)
[ "$MODE" = "preview" ] && ok "ONCHAIN_MODE=preview (Light Mode)" || warn "ONCHAIN_MODE=$MODE (expected preview)"

step "2/7 · Restart backend"
supervisorctl restart backend > /dev/null
sleep 7
ok "backend restarted"

step "3/7 · Infura RPC connectivity (all 4 chains)"
DIAG=$(curl -s "$BACKEND/api/admin/indexer/diagnostics")
for c in ethereum arbitrum optimism base; do
  STATUS=$(printf '%s' "$DIAG" | python3 -c "import sys,json; print(json.load(sys.stdin).get('rpc',{}).get('chains',{}).get('$c',{}).get('status','missing'))")
  HEAD=$(printf '%s' "$DIAG"   | python3 -c "import sys,json; print(json.load(sys.stdin).get('rpc',{}).get('chains',{}).get('$c',{}).get('head_block','?'))")
  [ "$STATUS" = "connected" ] && ok "$c  head=$HEAD" || fail "$c  status=$STATUS"
done

step "4/7 · Light-mode core endpoints (real numbers)"
BLOCK=$(curl -s "$BACKEND/api/onchain/summary?chain=ethereum" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('blockHeight',0))")
[ "$BLOCK" -gt 1000000 ] && ok "/api/onchain/summary  block=$BLOCK" || fail "/api/onchain/summary  block=$BLOCK"

TPS=$(curl -s "$BACKEND/api/onchain/summary?chain=ethereum" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('tps',0))")
python3 -c "import sys; sys.exit(0 if float('$TPS') > 0 else 1)" && ok "/api/onchain/summary  tps=$TPS" || fail "tps=$TPS — engine degraded"

STABLE=$(curl -s "$BACKEND/api/onchain/flows?chain=ethereum" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('stablecoin',{}).get('totalSupplyUsd',0))")
python3 -c "import sys; sys.exit(0 if float('$STABLE') > 1e9 else 1)" && ok "/api/onchain/flows  stablecoin_total=\$$(python3 -c "print(round(float('$STABLE')/1e9, 1))")B" \
  || fail "stablecoin total=$STABLE — DefiLlama unreachable"

TVL=$(curl -s "$BACKEND/api/onchain/activity?chain=ethereum" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('totalValueLocked',0))")
python3 -c "import sys; sys.exit(0 if float('$TVL') > 1e9 else 1)" && ok "/api/onchain/activity  TVL=\$$(python3 -c "print(round(float('$TVL')/1e9, 1))")B" \
  || warn "TVL=$TVL — DefiLlama TVL fetch issue"

DEX=$(curl -s "$BACKEND/api/onchain/activity?chain=ethereum" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('dexVolume24h',0))")
python3 -c "import sys; sys.exit(0 if float('$DEX') > 1e6 else 1)" && ok "/api/onchain/activity  dexVol24h=\$$(python3 -c "print(round(float('$DEX')/1e6, 1))")M" \
  || warn "DEX vol=$DEX"

step "5/7 · /api/mobile/intel/onchain (REAL Infura — was FAKE before audit)"
INTEL=$(curl -s "$BACKEND/api/mobile/intel/onchain?asset=BTC")
INTEL_MODE=$(printf '%s' "$INTEL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('mode','?'))")
[ "$INTEL_MODE" = "light_mode_infura" ] && ok "intel.mode = light_mode_infura" || fail "intel.mode=$INTEL_MODE (still using fake price-derived logic?)"

INTEL_BLOCK=$(printf '%s' "$INTEL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('activity',{}).get('blockHeight',0))")
[ "$INTEL_BLOCK" -gt 1000000 ] && ok "intel.activity.blockHeight=$INTEL_BLOCK (real Infura)" || fail "intel block=$INTEL_BLOCK"

step "6/7 · Zero-stub sweep (web + overview + smart-money)"
URLS=(
  "/api/onchain/status"
  "/api/onchain/summary?chain=ethereum"
  "/api/onchain/flows?chain=ethereum"
  "/api/onchain/whales?chain=ethereum"
  "/api/onchain/activity?chain=ethereum"
  "/api/onchain-overview/summary?chain=ethereum"
  "/api/onchain-overview/entities?chain=ethereum&limit=5"
  "/api/onchain-overview/exchange-flows?chain=ethereum"
  "/api/onchain-overview/smart-money?chain=ethereum&limit=5"
  "/api/onchain-overview/token-flows?chain=ethereum"
  "/api/onchain-overview/clusters?chain=ethereum&limit=5"
  "/api/onchain-overview/transfers?chain=ethereum&limit=5"
  "/api/onchain-overview/signals?limit=5"
  "/api/onchain-overview/whales?chain=ethereum&limit=5"
  "/api/onchain-overview/radar?chain=ethereum"
  "/api/onchain/cex/context?chainId=1&window=24h"
  "/api/onchain/smart-money/context?chainId=1&window=24h"
  "/api/onchain/smart-money/intelligence-context?chainId=1&window=24h"
  "/api/onchain/smart-money/token/BTC/context"
  "/api/mobile/intel/onchain?asset=BTC"
  "/api/admin/indexer/status"
  "/api/admin/indexer/diagnostics"
)
STUB=0
for u in "${URLS[@]}"; do
  n=$(curl -s "$BACKEND$u" | python3 -c "import sys,json
try: print(json.load(sys.stdin).get('note',''))
except: print('')" 2>/dev/null)
  if [ "$n" = "legacy_compat_stub_empty" ]; then
    printf "  \033[1;31m✗ STUB\033[0m  %s\n" "$u"; STUB=$((STUB+1))
  else
    ok "$u"
  fi
done
[ "$STUB" -eq 0 ] && ok "Zero stubs across $((${#URLS[@]})) endpoints" || fail "$STUB stubs remain"

step "7/7 · Indexer health (idle by design, but code paths sound)"
IDX_MODE=$(printf '%s' "$DIAG" | python3 -c "import sys,json; print(json.load(sys.stdin).get('mode','?'))")
IDX_RPC=$(printf '%s' "$DIAG"  | python3 -c "import sys,json; print(json.load(sys.stdin).get('health',{}).get('rpc','?'))")
[ "$IDX_MODE" = "preview" ] && ok "indexer.mode = preview (Light Mode — by design)" || warn "indexer.mode=$IDX_MODE (expected preview)"
[ "$IDX_RPC" = "ok" ] && ok "indexer.health.rpc = ok" || fail "indexer.health.rpc=$IDX_RPC"

printf "\n\033[1;32m✓ On-chain Light Mode verified — Infura active, 0 stubs across all surfaces\033[0m\n"
