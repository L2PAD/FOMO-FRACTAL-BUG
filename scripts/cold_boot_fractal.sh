#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# FOMO — Fractal & Meta Brain Cold Boot
#
# Brings the Fractal v2.1 engine + Meta Brain real-data pipeline up
# from scratch on a fresh deployment.  Idempotent — safe to re-run.
#
# This script is intentionally an extension of `cold_boot.sh`: run that
# FIRST, then this one (or use `bash scripts/bootstrap.sh` which calls
# both in order).  See `FRACTAL_DEPLOYMENT.md` for what each step does.
#
# Usage:
#   bash scripts/cold_boot_fractal.sh                # full bootstrap
#   bash scripts/cold_boot_fractal.sh --no-backfill  # skip 365d snapshot backfill
#   bash scripts/cold_boot_fractal.sh --verify-only  # just check endpoints
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; B='\033[0;34m'; N='\033[0m'
ok()   { echo -e "${G}✓${N} $*"; }
warn() { echo -e "${Y}⚠${N} $*"; }
err()  { echo -e "${R}✗${N} $*" >&2; }
info() { echo -e "${B}●${N} $*"; }

BACKFILL=1; VERIFY_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --no-backfill) BACKFILL=0 ;;
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) sed -n '1,18p' "$0"; exit 0 ;;
  esac
done

APP_ROOT="${APP_ROOT:-/app}"
cd "$APP_ROOT"

set -a; . "$APP_ROOT/backend/.env"; set +a

MONGO="${MONGO_URL:-mongodb://localhost:27017}"
DB="${DB_NAME:-fomo_mobile}"
PY="${PY:-/root/.venv/bin/python3}"
[ ! -x "$PY" ] && PY="$(command -v python3)"

# ── 1. Verify Node sidecar code exists ───────────────────────────────
info "[1/9] Verifying Node sidecar source tree…"
[ -d "$APP_ROOT/legacy/backend-src" ] || { err "/app/legacy/backend-src missing — repo wasn't cloned fully"; exit 1; }
[ -f "$APP_ROOT/legacy/sidecar-server.ts" ] || { err "sidecar-server.ts missing"; exit 1; }
ok "Sidecar TypeScript tree present (~22k LOC)"

# ── 2. Install Node deps (idempotent — only if not installed) ────────
info "[2/9] Ensuring Node deps under /app/legacy…"
if [ ! -d "$APP_ROOT/legacy/node_modules" ]; then
  if [ ! -f "$APP_ROOT/legacy/package.json" ]; then
    cp "$APP_ROOT/backend/package.json" "$APP_ROOT/legacy/package.json"
    cp "$APP_ROOT/backend/tsconfig.json" "$APP_ROOT/legacy/tsconfig.json"
    ln -sfn backend-src "$APP_ROOT/legacy/src"
  fi
  ( cd "$APP_ROOT/legacy" && yarn install --silent ) || { err "yarn install failed"; exit 1; }
  ok "yarn install complete"
else
  ok "node_modules already present"
fi

# ── 3. Memory-stubs for quarantined modules ──────────────────────────
info "[3/9] Ensuring fractal-engine memory stubs…"
STUB_DIR="$APP_ROOT/legacy/backend-src/modules/fractal/memory"
mkdir -p "$STUB_DIR/snapshot" "$STUB_DIR/outcome" "$STUB_DIR/attribution"
mkdir -p "$APP_ROOT/legacy/freeze"
[ -f "$APP_ROOT/legacy/freeze/freeze-manifest.json" ] || \
  echo '{"frozen":false,"stubbed":true}' > "$APP_ROOT/legacy/freeze/freeze-manifest.json"
ok "Memory stub directories ready (the .ts files are committed to the repo)"

# ── 4. Bootstrap canonical OHLCV from CSV seeds + live ───────────────
info "[4/9] Bootstrapping BTC/SPX/DXY canonical OHLCV into Mongo…"
$PY - <<PY
import os, csv, urllib.request
from datetime import datetime, timezone
from pymongo import MongoClient, UpdateOne, ASCENDING
client = MongoClient("$MONGO")
db = client["$DB"]
coll = db.fractal_canonical_ohlcv

def upsert_btc():
    """BTC: load from CSV bootstrap seeds, then fill recent gap from /api/ui/candles."""
    n_before = coll.count_documents({"meta.symbol": "BTC", "meta.timeframe": "1d"})
    if n_before >= 5000:
        print(f"  BTC already loaded ({n_before} candles), skipping CSV seed")
        return n_before
    # Pass 1: BTCUSD_daily.csv (CryptoDataDownload format)
    rows = {}
    fp = "$APP_ROOT/backend/data/fractal/bootstrap/BTCUSD_daily.csv"
    try:
        with open(fp) as f:
            lines = f.readlines()
        h_idx = next((i for i, l in enumerate(lines[:5]) if 'date' in l.lower() and ',' in l), 0)
        reader = csv.DictReader(lines[h_idx:])
        for row in reader:
            row = {(k or '').strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            ds = (row.get("date") or "").split(' ')[0][:10]
            try:
                dt = datetime.strptime(ds, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
                v = float(row.get("Volume USD") or row.get("Volume BTC") or 0)
                rows[ds] = (dt, o, h, l, c, v)
            except Exception:
                pass
    except FileNotFoundError:
        print("  BTCUSD_daily.csv not found")

    # Pass 2: BTC_legacy_2010.csv (Investing.com format)
    fp = "$APP_ROOT/backend/data/fractal/bootstrap/BTC_legacy_2010.csv"
    try:
        with open(fp, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ds = (row.get("Date") or "").strip().strip('"')
                try:
                    dt = datetime.strptime(ds, "%b %d, %Y").replace(tzinfo=timezone.utc)
                    def fnum(s): return float(str(s or "").replace('"', '').replace(',', ''))
                    c = fnum(row.get("Price"))
                    o = fnum(row.get("Open") or row.get("Price"))
                    h = fnum(row.get("High") or row.get("Price"))
                    l = fnum(row.get("Low") or row.get("Price"))
                    d_iso = dt.strftime("%Y-%m-%d")
                    if d_iso not in rows:
                        rows[d_iso] = (dt, o, h, l, c, 0)
                except Exception:
                    pass
    except FileNotFoundError:
        print("  BTC_legacy_2010.csv not found")

    ops = [
        UpdateOne(
            {"meta.symbol": "BTC", "meta.timeframe": "1d", "ts": dt},
            {"\$set": {
                "meta": {"symbol": "BTC", "timeframe": "1d"},
                "ts": dt,
                "ohlcv": {"o": o, "h": h, "l": l, "c": c, "v": v},
                "provenance": {"chosenSource": "PYTHON_BOOTSTRAP", "candidates": []},
                "quality": {"qualityScore": 1.0, "flags": [], "sanity_ok": True},
                "updatedAt": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        for d_iso, (dt, o, h, l, c, v) in rows.items()
    ]
    if ops:
        coll.bulk_write(ops, ordered=False)
    n_after = coll.count_documents({"meta.symbol": "BTC", "meta.timeframe": "1d"})
    print(f"  BTC: {n_after} daily candles loaded")
    return n_after

upsert_btc()

# Bridge the recent gap from /api/ui/candles (Python-served)
try:
    r = urllib.request.urlopen("http://127.0.0.1:8001/api/ui/candles?asset=BTC&years=2", timeout=15)
    import json
    candles = json.loads(r.read()).get("candles", [])
    existing = {d["ts"].strftime("%Y-%m-%d") for d in coll.find({"meta.symbol":"BTC","meta.timeframe":"1d"}, {"ts":1, "_id":0})}
    ops = []
    for k in candles:
        ts = (k.get("t") or "").split("T")[0]
        if not ts or ts in existing: continue
        dt = datetime.strptime(ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        ops.append(UpdateOne(
            {"meta.symbol": "BTC", "meta.timeframe": "1d", "ts": dt},
            {"\$set": {
                "meta": {"symbol":"BTC","timeframe":"1d"}, "ts": dt,
                "ohlcv": {"o": float(k["o"]), "h": float(k["h"]), "l": float(k["l"]), "c": float(k["c"]), "v": float(k.get("v") or 0)},
                "provenance": {"chosenSource": "PY_UI_CANDLES"},
                "quality": {"qualityScore": 1.0, "sanity_ok": True},
            }}, upsert=True))
    if ops:
        coll.bulk_write(ops, ordered=False)
        print(f"  BTC: gap filled, +{len(ops)} candles from live source")
except Exception as e:
    print(f"  BTC live-gap fill skipped: {e}")
PY
ok "BTC canonical OHLCV ready"

# ── 5. Add Node sidecar to supervisor ────────────────────────────────
info "[5/9] Registering Node sidecar in supervisor…"
if [ ! -f /etc/supervisor/conf.d/supervisord_node_sidecar.conf ]; then
  cat > /etc/supervisor/conf.d/supervisord_node_sidecar.conf <<EOF
[program:node_sidecar]
command=$APP_ROOT/legacy/node_modules/.bin/tsx $APP_ROOT/legacy/sidecar-server.ts
directory=$APP_ROOT/legacy
autostart=true
autorestart=true
startretries=5
startsecs=120
stopwaitsecs=30
environment=MONGODB_URI="$MONGO/$DB",NODE_SIDECAR_PORT="8003",PORT="8003",NODE_ENV="production",LOG_LEVEL="warn",CORS_ORIGINS="*"
stdout_logfile=/var/log/supervisor/node_sidecar.out.log
stderr_logfile=/var/log/supervisor/node_sidecar.err.log
stdout_logfile_maxbytes=10MB
stderr_logfile_maxbytes=10MB
stopasgroup=true
killasgroup=true
priority=900
EOF
  ok "Node sidecar supervisor config written"
else
  ok "Node sidecar supervisor config already present"
fi

# ── 6. Add rolling forecast loop to supervisor ───────────────────────
info "[6/9] Registering rolling-forecast loop in supervisor…"
if [ ! -f /etc/supervisor/conf.d/supervisord_rolling_forecast.conf ]; then
  cat > /etc/supervisor/conf.d/supervisord_rolling_forecast.conf <<EOF
[program:rolling_forecast_loop]
command=$PY $APP_ROOT/backend/scripts/rolling_forecast_loop.py
directory=$APP_ROOT/backend
autostart=true
autorestart=true
startretries=5
startsecs=10
stopwaitsecs=30
environment=MONGO_URL="$MONGO",DB_NAME="$DB",ROLLING_LOOP_INTERVAL="21600",PYTHONUNBUFFERED="1"
stdout_logfile=/var/log/supervisor/rolling_forecast_loop.out.log
stderr_logfile=/var/log/supervisor/rolling_forecast_loop.err.log
stdout_logfile_maxbytes=5MB
stderr_logfile_maxbytes=5MB
stopasgroup=true
killasgroup=true
priority=920
EOF
  ok "Rolling-forecast loop supervisor config written"
else
  ok "Rolling-forecast loop supervisor config already present"
fi

supervisorctl reread > /dev/null
supervisorctl update > /dev/null
ok "Supervisor reloaded"

# ── 7. Wait for Node sidecar to mount fractal plugin ─────────────────
info "[7/9] Waiting for Node sidecar to boot (up to 90s)…"
mounted=0
for i in $(seq 1 45); do
  if grep -q "Fractal engine plugin mounted" /var/log/supervisor/node_sidecar.out.log 2>/dev/null; then
    mounted=1; break
  fi
  sleep 2
done
if [ "$mounted" = 1 ]; then
  ok "Node sidecar mounted Fractal v2.1 engine on :8003"
else
  warn "Fractal plugin did not report mounted in 90s — check /var/log/supervisor/node_sidecar.out.log"
fi

# ── 8. Backfill 365 days of rolling forecast snapshots ───────────────
if [ "$BACKFILL" = 1 ] && [ "$VERIFY_ONLY" != 1 ]; then
  info "[8/9] Backfilling 365 days of BTC rolling-forecast snapshots…"
  cnt=$($PY -c "from pymongo import MongoClient; print(MongoClient('$MONGO')['$DB'].fractal_rolling_snapshots.count_documents({'asset':'BTC','metadata.source':'rolling_v1'}))" 2>/dev/null || echo 0)
  if [ "$cnt" -lt 100 ]; then
    $PY "$APP_ROOT/backend/scripts/backfill_rolling_forecasts.py" --days 365 --stride 3 --horizon 30 --window 120 --topk 10
    ok "Rolling-forecast backfill complete"
  else
    ok "Rolling-forecast snapshots already populated ($cnt docs)"
  fi
else
  warn "[8/9] Skipping backfill (--no-backfill or --verify-only)"
fi

# ── 9. Restart FastAPI so it picks up new proxy routers ──────────────
info "[9/9] Restarting backend…"
supervisorctl restart backend > /dev/null 2>&1 || true
sleep 5

# ── Smoke test ───────────────────────────────────────────────────────
info "Running smoke tests against http://127.0.0.1:8001…"
pass=0; fail=0
for ep in \
  "/api/fractal/v2.1/overlay?symbol=BTC&horizon=30&windowLen=120&topK=10&aftermathDays=30" \
  "/api/fractal/dxy?focus=30d" \
  "/api/fractal/spx?focus=30d" \
  "/api/overlay/coeffs?base=BTC&driver=SPX&horizon=30d" \
  "/api/ui/overview?asset=btc&horizon=90" \
  "/api/prediction/snapshots?asset=BTC&view=hybrid&horizon=90&limit=10" \
  "/api/meta-brain-v2/status" \
  "/api/meta-brain-v2/correlation?window_days=120" \
  "/api/mbrain/verdicts/list?limit=5" \
  ; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8001$ep")
  if [ "$code" = "200" ]; then
    pass=$((pass+1)); echo "  ${G}✓${N} HTTP $code  $ep"
  else
    fail=$((fail+1)); echo "  ${R}✗${N} HTTP $code  $ep"
  fi
done

echo ""
if [ "$fail" = 0 ]; then
  ok "Fractal cold-boot complete — $pass/$pass endpoints healthy."
  echo "   ▸ Web overview:   ${APP_URL:-http://localhost:3000}/fractal/overview"
  echo "   ▸ Node sidecar:   http://127.0.0.1:8003 (logs: /var/log/supervisor/node_sidecar.out.log)"
  echo "   ▸ Auto-update:    supervisorctl status rolling_forecast_loop"
else
  warn "Fractal cold-boot finished — $pass passed, $fail failed.  See FRACTAL_DEPLOYMENT.md → Troubleshooting."
fi
