#!/bin/bash

# GOLDEN PATHS — FINAL RUN (P1.4)
# ================================
# Tests critical paths via API before P2 merge

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "GOLDEN PATHS — FINAL RUN"
echo "═══════════════════════════════════════════════════════════════"
echo ""

PASSED=0
FAILED=0
API="http://localhost:8003"

test_pass() {
    echo "✅ $1"
    ((PASSED++))
}

test_fail() {
    echo "❌ $1"
    echo "   $2"
    ((FAILED++))
}

# ═══════════════════════════════════════════════════════════════
# GP1: Meta-Brain verdict includes invariant check
# ═══════════════════════════════════════════════════════════════

echo "GP1: Meta-Brain includes invariant check"

RESULT=$(curl -s -X POST "$API/api/v10/meta-brain/simulate" \
    -H "Content-Type: application/json" \
    -d '{"symbol":"BTCUSDT"}')

if echo "$RESULT" | grep -q '"invariantCheck"'; then
    test_pass "Verdict includes invariantCheck"
else
    test_fail "Verdict missing invariantCheck" "$RESULT"
fi

if echo "$RESULT" | grep -q '"macroContext"'; then
    test_pass "Verdict includes macroContext"
else
    test_fail "Verdict missing macroContext" "$RESULT"
fi

# ═══════════════════════════════════════════════════════════════
# GP2: Admin system-status works
# ═══════════════════════════════════════════════════════════════

echo ""
echo "GP2: Admin visibility"

RESULT=$(curl -s "$API/api/v10/admin/system-status")

if echo "$RESULT" | grep -q '"ok":true'; then
    test_pass "Admin system-status returns OK"
else
    test_fail "Admin system-status failed" "$RESULT"
fi

if echo "$RESULT" | grep -q '"invariants"'; then
    test_pass "System-status includes invariants info"
else
    test_fail "System-status missing invariants" "$RESULT"
fi

if echo "$RESULT" | grep -q '"lockdown"'; then
    test_pass "System-status includes lockdown state"
else
    test_fail "System-status missing lockdown" "$RESULT"
fi

# ═══════════════════════════════════════════════════════════════
# GP3: Kill switches work
# ═══════════════════════════════════════════════════════════════

echo ""
echo "GP3: Kill switches operational"

RESULT=$(curl -s "$API/api/v10/admin/kill-switches")

if echo "$RESULT" | grep -q '"mlInfluence"'; then
    test_pass "Kill switches endpoint works"
else
    test_fail "Kill switches endpoint failed" "$RESULT"
fi

# ═══════════════════════════════════════════════════════════════
# GP4: Lockdown state available
# ═══════════════════════════════════════════════════════════════

echo ""
echo "GP4: Lockdown state"

RESULT=$(curl -s "$API/api/v10/admin/lockdown-state")

if echo "$RESULT" | grep -q '"LOCKED_PRE_MERGE"'; then
    test_pass "Lockdown state is LOCKED_PRE_MERGE"
else
    test_fail "Lockdown state incorrect" "$RESULT"
fi

# ═══════════════════════════════════════════════════════════════
# GP5: Regime history API works
# ═══════════════════════════════════════════════════════════════

echo ""
echo "GP5: Regime history"

RESULT=$(curl -s "$API/api/v10/macro-intel/regime/history?limit=3")

if echo "$RESULT" | grep -q '"ok":true'; then
    test_pass "Regime history endpoint works"
else
    test_fail "Regime history endpoint failed" "$RESULT"
fi

# ═══════════════════════════════════════════════════════════════
# GP6: MLOps state endpoint works
# ═══════════════════════════════════════════════════════════════

echo ""
echo "GP6: MLOps state"

RESULT=$(curl -s "$API/api/v10/mlops/state")

if echo "$RESULT" | grep -q '"ok":true'; then
    test_pass "MLOps state endpoint works"
else
    test_fail "MLOps state endpoint failed" "$RESULT"
fi

# ═══════════════════════════════════════════════════════════════
# GP7: Health check
# ═══════════════════════════════════════════════════════════════

echo ""
echo "GP7: System health"

RESULT=$(curl -s "$API/api/health")

if echo "$RESULT" | grep -q '"ok":true'; then
    test_pass "Health check passes"
else
    test_fail "Health check failed" "$RESULT"
fi

# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "RESULT: $PASSED passed, $FAILED failed"
echo "═══════════════════════════════════════════════════════════════"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "❌ GOLDEN PATHS FAILED — DO NOT PROCEED WITH P2 MERGE"
    exit 1
else
    echo ""
    echo "✅ ALL GOLDEN PATHS PASSED — SAFE TO PROCEED WITH P2 MERGE"
    exit 0
fi
