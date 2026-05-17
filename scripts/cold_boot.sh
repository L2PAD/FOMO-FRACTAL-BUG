#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# FOMO — Cold Boot Script
#
# Brings a fresh deployment from zero to ready. Idempotent: safe to
# re-run. See DEPLOYMENT.md for what each step does.
#
# Usage:
#   bash scripts/cold_boot.sh                 # full boot with replay
#   bash scripts/cold_boot.sh --no-replay     # skip historical forecast replay
#   bash scripts/cold_boot.sh --verify-only   # just check envs + mongo ping
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# Colors
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; B='\033[0;34m'; N='\033[0m'
ok()  { echo -e "${G}✓${N} $*"; }
warn(){ echo -e "${Y}⚠${N} $*"; }
err() { echo -e "${R}✗${N} $*" >&2; }
info(){ echo -e "${B}●${N} $*"; }

# Args
REPLAY=1; VERIFY_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --no-replay) REPLAY=0 ;;
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
  esac
done

APP_ROOT="${APP_ROOT:-/app}"
cd "$APP_ROOT"

# ── 1. Verify envs ───────────────────────────────────────────────────
info "[1/8] Verifying environment files…"
[ -f "$APP_ROOT/backend/.env" ] || { err "backend/.env missing. Copy from backend/.env.example."; exit 1; }
[ -f "$APP_ROOT/frontend/.env" ] || { err "frontend/.env missing. Copy from frontend/.env.example."; exit 1; }

set -a; . "$APP_ROOT/backend/.env"; set +a

REQUIRED_BACKEND=(MONGO_URL DB_NAME GOOGLE_CLIENT_ID JWT_ACCESS_SECRET JWT_REFRESH_SECRET COOKIE_ENC_KEY)
MISSING=()
for k in "${REQUIRED_BACKEND[@]}"; do
  if [ -z "${!k:-}" ]; then MISSING+=("$k"); fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
  err "Missing required env vars: ${MISSING[*]}"
  echo "    Fill them in backend/.env and re-run."
  exit 1
fi
ok "Required envs present"

# Soft-required (warn, don't fail)
for k in MINIAPP_BOT_TOKEN MINIAPP_URL EMERGENT_LLM_KEY NOWPAYMENTS_API_KEY INFURA_KEY APP_URL; do
  [ -z "${!k:-}" ] && warn "$k not set — related module will run degraded or be skipped"
done

# ── 2. Mongo ping ────────────────────────────────────────────────────
info "[2/8] Pinging MongoDB at $MONGO_URL…"
if command -v mongosh >/dev/null 2>&1; then
  mongosh --quiet --eval 'db.runCommand({ping:1}).ok' "$MONGO_URL" > /dev/null || { err "Mongo not reachable"; exit 1; }
elif command -v mongo >/dev/null 2>&1; then
  mongo --quiet --eval 'db.adminCommand("ping").ok' "$MONGO_URL" > /dev/null || { err "Mongo not reachable"; exit 1; }
else
  python3 -c "from pymongo import MongoClient; import os; MongoClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=3000).admin.command('ping')" || { err "Mongo not reachable"; exit 1; }
fi
ok "Mongo reachable"

if [ "$VERIFY_ONLY" = 1 ]; then
  ok "Verify-only mode — done."
  exit 0
fi

# ── 2.5. Phase E1 — Regenerate shared i18n snapshot ──────────────────
# The TG Mini-App reads backend/services/i18n_dictionary.json on every
# /api/miniapp/lite request. The snapshot is generated from the canonical
# frontend/src/core/i18n.ts via a pure-Node parser. Regenerate on every
# cold boot so the snapshot can't drift from source.
info "[2.5/8] Phase E1 — Regenerating shared i18n dictionary snapshot…"
if command -v node >/dev/null 2>&1; then
  ( cd "$APP_ROOT/frontend" && node scripts/generate-i18n-json.cjs ) || {
    err "i18n generator failed — check frontend/src/core/i18n.ts syntax"; exit 1;
  }
  # Parity invariant: en/ru/uk must agree on key count
  python3 - <<'PY'
import json, sys
p = '/app/backend/services/i18n_dictionary.json'
d = json.load(open(p))['dictionary']
counts = {l: len(d.get(l, {})) for l in ('en','ru','uk')}
if not (counts['en'] == counts['ru'] == counts['uk']):
    print(f"i18n parity broken: {counts}", file=sys.stderr); sys.exit(1)
print(f"i18n parity OK: en={counts['en']} ru={counts['ru']} uk={counts['uk']}")
PY
  ok "i18n snapshot regenerated, parity verified"
else
  warn "node not found — using committed backend/services/i18n_dictionary.json as-is (may be stale)"
fi

# ── 3. Indexes + seed dev user ───────────────────────────────────────
info "[3/8] Creating indexes + seeding dev user…"
python3 "$APP_ROOT/backend/bootstrap_cold_start.py"
ok "Indexes + dev user ready"

# ── 4. Seed admin account ────────────────────────────────────────────
info "[4/8] Seeding default admin (admin / admin12345)…"
python3 - <<'PY'
import os, sys
sys.path.insert(0, '/app/backend')
from pymongo import MongoClient
import bcrypt
from datetime import datetime
client = MongoClient(os.environ['MONGO_URL'])
db = client[os.environ.get('DB_NAME', 'test_database')]
if not db.admin_accounts.find_one({'username': 'admin'}):
    db.admin_accounts.insert_one({
        'username': 'admin',
        'password_hash': bcrypt.hashpw(b'admin12345', bcrypt.gensalt()).decode(),
        'role': 'superadmin',
        'created_at': datetime.utcnow(),
    })
    print('[seed] admin account created')
else:
    print('[seed] admin account already exists')
PY

# Persist credentials so the testing agent / fork agent can find them
mkdir -p "$APP_ROOT/memory"
cat > "$APP_ROOT/memory/test_credentials.md" <<EOF
# Test credentials (generated by cold_boot.sh)

| Surface              | Username      | Password    |
|----------------------|---------------|-------------|
| Admin panel          | admin         | admin12345  |
| Dev user (Google)    | dev@fomo.ai   | —           |
EOF
ok "Admin + dev creds seeded → memory/test_credentials.md"

# ── 5. Seed info_cms_config ──────────────────────────────────────────
info "[5/8] Seeding /info CMS defaults…"
python3 - <<'PY'
import os, sys
sys.path.insert(0, '/app/backend')
from pymongo import MongoClient
client = MongoClient(os.environ['MONGO_URL'])
db = client[os.environ.get('DB_NAME', 'test_database')]
if db.info_cms_config.count_documents({'_id': 'main'}) == 0:
    db.info_cms_config.insert_one({
        '_id': 'main',
        'app_links': {
            'android':  {'url': '', 'status': 'soon'},
            'ios':      {'url': '', 'status': 'soon'},
            'telegram': {'url': 'https://t.me/FOMO_mini_bot/app', 'status': 'live'},
        },
        'legal_pages': {'terms': '', 'privacy': '', 'cookies': ''},
        'social_links': {'twitter': '', 'discord': '', 'telegram': '', 'linkedin': ''},
        'updated_at': None,
        'updated_by': None,
    })
    print('[seed] info_cms_config initialised')
else:
    print('[seed] info_cms_config already present')
PY
ok "/info CMS defaults ready"

# ── 6. Register Telegram webhook (if configured) ─────────────────────
if [ -n "${MINIAPP_BOT_TOKEN:-}" ] && [ -n "${APP_URL:-}" ]; then
  info "[6/8] Registering Telegram webhook → $APP_URL/api/miniapp/telegram/webhook"
  curl -s -X POST "https://api.telegram.org/bot${MINIAPP_BOT_TOKEN}/setWebhook" \
       -d "url=${APP_URL}/api/miniapp/telegram/webhook" \
       -d 'allowed_updates=["message","callback_query"]' | grep -q '"ok":true' \
    && ok "Webhook registered" \
    || warn "Webhook registration returned non-ok — check MINIAPP_BOT_TOKEN + APP_URL"
else
  warn "[6/8] Skipping webhook (MINIAPP_BOT_TOKEN or APP_URL missing)"
fi

# ── 7. Historical forecast replay ────────────────────────────────────
if [ "$REPLAY" = 1 ]; then
  info "[7/8] Replaying historical forecasts for BTC/ETH/SOL (this may take 1-3 minutes)…"
  for asset in BTC ETH SOL; do
    if [ -n "${APP_URL:-}" ]; then
      curl -s -X POST "${APP_URL}/api/system/bootstrap/replay?start=2024-01-01&asset=${asset}" \
           -o /tmp/replay-$asset.json -w "  $asset → HTTP %{http_code}\n" || true
    else
      # fallback: call locally
      curl -s -X POST "http://localhost:8001/api/system/bootstrap/replay?start=2024-01-01&asset=${asset}" \
           -o /tmp/replay-$asset.json -w "  $asset → HTTP %{http_code}\n" || true
    fi
  done
  ok "Replay complete (check /tmp/replay-*.json for details)"
else
  warn "[7/8] Skipping historical replay (--no-replay)"
fi

# ── 8. Restart services ──────────────────────────────────────────────
info "[8/8] Restarting services…"
if command -v supervisorctl >/dev/null 2>&1; then
  sudo supervisorctl restart backend expo 2>&1 | sed 's/^/    /'
  ok "Services restarted"
else
  warn "supervisorctl not available — start services manually: uvicorn + expo start"
fi

echo ""
ok "Cold boot complete."
echo "   ▸ Web landing:    ${APP_URL:-http://localhost:3000}/info"
echo "   ▸ Admin panel:    ${APP_URL:-http://localhost:8001}/api/panel/admin/intel"
echo "   ▸ MiniApp bot:    https://t.me/FOMO_mini_bot"
echo "   ▸ Module manager: bash scripts/module_manager.sh status"
