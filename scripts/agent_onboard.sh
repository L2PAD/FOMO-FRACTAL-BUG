#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# FOMO OS · Agent Onboarding Script
# ─────────────────────────────────────────────────────────────────────
# Запускается следующим агентом при старте сессии.
# Выводит:
#   • health всех сервисов
#   • состояние production universe (11 активов)
#   • backend regression smoke (≤30s)
#   • ссылки на актуальные аудит-документы
#   • known deferred workstreams
#
# Использование:
#   bash /app/scripts/agent_onboard.sh           # полный режим
#   bash /app/scripts/agent_onboard.sh --quick   # только health, без regression
#
# Exit code:
#   0 — система в production-grade baseline
#   1 — деградация (есть failures в regression или нет critical сервисов)
# ─────────────────────────────────────────────────────────────────────

set -uo pipefail

MODE="${1:-full}"

# Colors
B='\033[1m'; G='\033[32m'; Y='\033[33m'; R='\033[31m'; C='\033[36m'; D='\033[2m'; N='\033[0m'

echo -e "${B}╔════════════════════════════════════════════════════════════════╗${N}"
echo -e "${B}║          FOMO OS · Agent Onboarding ($(date -u +%Y-%m-%d))               ║${N}"
echo -e "${B}╚════════════════════════════════════════════════════════════════╝${N}"
echo

# ── 1. Identity / project layout ────────────────────────────────────
echo -e "${B}[1] Project layout${N}"
for d in backend frontend mobile backend/core_universe.py docs/audit memory tests/p2; do
    if [[ -e "/app/$d" ]]; then
        echo -e "  ${G}✓${N} /app/$d"
    else
        echo -e "  ${R}✗${N} /app/$d ${R}(missing!)${N}"
    fi
done
echo

# ── 2. Service health ───────────────────────────────────────────────
echo -e "${B}[2] Supervisor service status${N}"
if command -v supervisorctl >/dev/null 2>&1; then
    SUP_OUT=$(supervisorctl status 2>&1)
    while IFS= read -r line; do
        case "$line" in
            *RUNNING*) echo -e "  ${G}✓${N} $line" ;;
            *STOPPED*|*FATAL*|*BACKOFF*) echo -e "  ${R}✗${N} $line" ;;
            *STARTING*) echo -e "  ${Y}…${N} $line" ;;
            *) echo -e "    $line" ;;
        esac
    done <<< "$SUP_OUT"
else
    echo -e "  ${R}supervisorctl not available${N}"
fi
echo

# ── 3. Backend health probe ─────────────────────────────────────────
echo -e "${B}[3] Backend health probe${N}"
BACKEND_UP=0
HEALTH=$(curl -s --max-time 5 http://localhost:8001/api/health 2>/dev/null)
if [[ -n "$HEALTH" ]]; then
    echo -e "  ${G}✓${N} /api/health → ${D}$HEALTH${N}" | head -c 200
    echo
    BACKEND_UP=1
else
    echo -e "  ${R}✗${N} /api/health unreachable on localhost:8001"
fi

# Symbol canonicalization smoke
if [[ $BACKEND_UP -eq 1 ]]; then
    BTC_RAW=$(curl -s --max-time 5 -H "X-User-Id: onboard" -H "X-User-Email: o@l" \
                "http://localhost:8001/api/trading/verdict/BTCUSDT" 2>/dev/null)
    CANON=$(echo "$BTC_RAW" | python3 -c "import json,sys; print(json.load(sys.stdin).get('canonicalSymbol','?'))" 2>/dev/null)
    if [[ "$CANON" == "BTC" ]]; then
        echo -e "  ${G}✓${N} Symbol canonicalization: BTCUSDT → BTC ${D}(P1-A patch active)${N}"
    else
        echo -e "  ${R}✗${N} Symbol canonicalization broken: BTCUSDT → ${R}$CANON${N}"
    fi
fi
echo

# ── 4. Production universe snapshot ─────────────────────────────────
if [[ $BACKEND_UP -eq 1 ]]; then
    echo -e "${B}[4] Production universe (verdict snapshot)${N}"
    echo -e "  ${D}Symbol  Action  Conf   Active modules${N}"
    for s in BTC ETH SOL DOGE LINK AVAX ARB OP ADA BNB XRP; do
        VR=$(curl -s --max-time 6 -H "X-User-Id: onboard" -H "X-User-Email: o@l" \
                "http://localhost:8001/api/trading/verdict/$s" 2>/dev/null)
        if [[ -z "$VR" ]]; then
            echo -e "  ${R}✗${N} $s — no response"
            continue
        fi
        SUMMARY=$(echo "$VR" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    al=d.get('alignment',{})
    am=al.get('activeModules',[])
    print(f\"{d.get('canonicalSymbol','?'):>4s}   {d.get('action','?'):<5s}  {d.get('confidence',0):.3f}  {len(am)}/5: {','.join(am)}\")
except Exception as e:
    print('ERR', e)
" 2>/dev/null)
        # color row based on active count
        ACTIVE_N=$(echo "$SUMMARY" | grep -oE '[0-9]/5' | head -1 | cut -d/ -f1)
        if [[ "$ACTIVE_N" == "4" || "$ACTIVE_N" == "5" ]]; then
            echo -e "  ${G}✓${N} $SUMMARY"
        elif [[ "$ACTIVE_N" == "3" ]]; then
            echo -e "  ${Y}~${N} $SUMMARY"
        else
            echo -e "  ${R}!${N} $SUMMARY"
        fi
    done
    echo
fi

# ── 5. Backend regression (full mode) ───────────────────────────────
REGR_EXIT=0
if [[ "$MODE" != "--quick" ]] && [[ $BACKEND_UP -eq 1 ]]; then
    echo -e "${B}[5] Backend regression suite${N}"
    echo -e "  ${D}Running /app/tests/p2/regression.py …${N}"
    if [[ -f /app/tests/p2/regression.py ]]; then
        REG_OUT=$(python3 /app/tests/p2/regression.py 2>&1)
        REGR_EXIT=$?
        SUMMARY_LINE=$(echo "$REG_OUT" | grep -E "Checks total|Passed|Failed|Warnings|Overall" | head -10)
        while IFS= read -r line; do
            if [[ "$line" == *PASS* ]] || [[ "$line" == *Passed* ]]; then
                echo -e "  ${G}$line${N}"
            elif [[ "$line" == *FAIL* ]] || [[ "$line" == *Failed* ]]; then
                if [[ "$line" == *": 0"* ]]; then
                    echo -e "  ${G}$line${N}"
                else
                    echo -e "  ${R}$line${N}"
                fi
            else
                echo -e "  $line"
            fi
        done <<< "$SUMMARY_LINE"
    else
        echo -e "  ${R}✗${N} /app/tests/p2/regression.py отсутствует"
        REGR_EXIT=1
    fi
    echo
fi

# ── 6. Audit documents ──────────────────────────────────────────────
echo -e "${B}[6] Audit documents (читай ДО любых правок)${N}"
DOCS=(
    "docs/audit/SESSION_AUDIT_2026-05-15.md|Что сделано в P1/P2 · production state · contract"
    "docs/audit/REPOSITORY_FINDINGS_2026-05-15.md|Root cause missing Terminal · 3 репозитория"
    "memory/RCA_VERDICT_AGGREGATOR_2026-05-15.md|Forensic анализ symbol normalization"
    "memory/P1_ACCEPTANCE_2026-05-15.md|Production Readiness Matrix"
    "memory/P2_BACKEND_REGRESSION_2026-05-15.md|Полный лог 186/186"
    "memory/P2_ACCEPTANCE_2026-05-15.md|Freeze baseline contract"
    "AGENT_ONBOARDING.md|ЭТОТ файл — главный onboarding"
)
for d in "${DOCS[@]}"; do
    IFS='|' read -r path desc <<< "$d"
    if [[ -f "/app/$path" ]]; then
        echo -e "  ${G}✓${N} ${C}/app/$path${N}"
        echo -e "      ${D}$desc${N}"
    else
        echo -e "  ${R}✗${N} /app/$path ${R}(missing)${N}"
    fi
done
echo

# ── 7. Deferred workstreams ─────────────────────────────────────────
echo -e "${B}[7] Deferred workstreams (НЕ начинай без согласования)${N}"
echo -e "  ${Y}P-Terminal${N}  Drop-in restore Terminal UI из github.com/L2PAD/F-TRADE-FINAL"
echo -e "              ${D}(plan: docs/audit/REPOSITORY_FINDINGS_2026-05-15.md § Recommendation)${N}"
echo -e "  ${Y}P3${N}          Sentiment substrate · Twitter L0-L2 / actor graph / weighting"
echo -e "              ${D}БЕЗ LLM backfill — указание оператора${N}"
echo -e "  ${Y}P4${N}          OnChain per-asset (сейчас symbol-agnostic ethereum-chain)"
echo -e "  ${Y}P5${N}          MetaBrain calibration — thresholds tuning"
echo -e "  ${Y}UI-debt${N}     MetaBrain Coverage 0/4 → repoint на /api/trading/verdict"
echo

# ── 8. Untouchable surfaces ─────────────────────────────────────────
echo -e "${B}[8] ${R}НЕ ТРОГАТЬ без явного разрешения${N}"
echo -e "  ${R}✗${N} backend/services/sentiment_runtime.py    ${D}(P3 workstream)${N}"
echo -e "  ${R}✗${N} backend/services/fractal_runtime.py      ${D}(стабилизирован)${N}"
echo -e "  ${R}✗${N} backend/routes/legacy_compat.py          ${D}(honest fallback, не маскер)${N}"
echo -e "  ${R}✗${N} build_verdict() consensus logic          ${D}(P5 workstream)${N}"
echo -e "  ${R}✗${N} PriceExpectationV2Page.jsx tab 'ta'      ${D}(pre-existing placeholder)${N}"
echo

# ── 9. Final verdict ────────────────────────────────────────────────
echo -e "${B}═══════════════════════════════════════════════════════════════${N}"
if [[ $BACKEND_UP -eq 1 ]] && [[ $REGR_EXIT -eq 0 ]]; then
    echo -e "  ${G}✅ System in production-grade baseline — safe to continue${N}"
    echo -e "  ${D}Прочитай AGENT_ONBOARDING.md и docs/audit/* перед правками${N}"
    EXIT=0
else
    echo -e "  ${R}⚠️  Detected degradation — fix before adding features${N}"
    [[ $BACKEND_UP -ne 1 ]] && echo -e "  ${R}   → Backend unreachable${N}"
    [[ $REGR_EXIT -ne 0 ]] && echo -e "  ${R}   → Regression suite failed${N}"
    EXIT=1
fi
echo -e "${B}═══════════════════════════════════════════════════════════════${N}"

exit $EXIT
