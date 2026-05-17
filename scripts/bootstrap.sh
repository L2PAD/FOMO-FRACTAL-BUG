#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# FOMO OS — Bootstrap script
# ─────────────────────────────────────────────────────────────────────────────
# Полное развёртывание системы: env-check → deps → services → seed → verify.
# Идемпотентен: можно запускать несколько раз подряд безопасно.
#
# Usage:
#   bash /app/scripts/bootstrap.sh                     # full bootstrap
#   bash /app/scripts/bootstrap.sh --skip-deps         # пропустить установку пакетов
#   bash /app/scripts/bootstrap.sh --skip-seed         # пропустить seed данных
#   bash /app/scripts/bootstrap.sh --verify-only       # только верификация
# ─────────────────────────────────────────────────────────────────────────────
set -e

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GRN}✓${NC} $*"; }
warn() { echo -e "${YLW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }
hdr()  { echo -e "\n${BLU}══ $* ══${NC}"; }

# ── Flags ────────────────────────────────────────────────────────────────────
SKIP_DEPS=0; SKIP_SEED=0; VERIFY_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --skip-deps)    SKIP_DEPS=1 ;;
    --skip-seed)    SKIP_SEED=1 ;;
    --verify-only)  VERIFY_ONLY=1; SKIP_DEPS=1; SKIP_SEED=1 ;;
    *) warn "Unknown flag: $arg" ;;
  esac
done

cd /app

# ─────────────────────────────────────────────────────────────────────────────
# 1) ENV CHECK
# ─────────────────────────────────────────────────────────────────────────────
hdr "1. ENV CHECK"

if [ ! -f backend/.env ]; then
  err "backend/.env отсутствует. Создайте его с MONGO_URL и DB_NAME."
  exit 1
fi

if ! grep -q '^MONGO_URL=' backend/.env; then
  err "MONGO_URL не задан в backend/.env"
  exit 1
fi
if ! grep -q '^DB_NAME=' backend/.env; then
  warn "DB_NAME не задан — по умолчанию будет 'fomo_mobile'"
fi

if [ ! -f frontend/.env ]; then
  err "frontend/.env отсутствует"
  exit 1
fi
if ! grep -q '^REACT_APP_BACKEND_URL=' frontend/.env; then
  err "REACT_APP_BACKEND_URL не задан в frontend/.env"
  exit 1
fi

ok "backend/.env и frontend/.env найдены и валидны"

# Загружаем env для подскрипт-вызовов
set -a
. ./backend/.env
set +a
export MONGO_URL DB_NAME

# ─────────────────────────────────────────────────────────────────────────────
# 2) DEPS
# ─────────────────────────────────────────────────────────────────────────────
if [ "$SKIP_DEPS" -eq 0 ]; then
  hdr "2. DEPENDENCIES"
  
  echo "→ Python (backend/requirements.txt)..."
  pip install --quiet -r backend/requirements.txt 2>&1 | tail -3
  ok "Python deps готовы"
  
  echo "→ Node (frontend/package.json via yarn)..."
  if [ ! -d frontend/node_modules ]; then
    cd frontend && yarn install --silent 2>&1 | tail -5 && cd ..
  fi
  ok "Frontend deps готовы (yarn)"
else
  warn "Skipping deps (--skip-deps)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3) SERVICES
# ─────────────────────────────────────────────────────────────────────────────
hdr "3. SUPERVISOR SERVICES"

# Restart backend & frontend если deps менялись
if [ "$SKIP_DEPS" -eq 0 ]; then
  supervisorctl restart backend frontend news_substrate 2>&1 | tail -5
  echo "→ Waiting for backend to come up..."
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/ | grep -qE '^(200|404)$'; then
      ok "backend отвечает на :8001"
      break
    fi
    sleep 2
  done
fi

supervisorctl status | grep -E "backend|frontend|mongodb|news_substrate" || true

# ─────────────────────────────────────────────────────────────────────────────
# 4) SEED / INITIAL DATA
# ─────────────────────────────────────────────────────────────────────────────
if [ "$SKIP_SEED" -eq 0 ]; then
  hdr "4. SEED DATA"
  
  cd backend
  
  # 4a) Indexes
  echo "→ Creating MongoDB indexes..."
  python -c "
from pymongo import MongoClient
import os
client = MongoClient(os.environ.get('MONGO_URL'))
db = client[os.environ.get('DB_NAME', 'fomo_mobile')]
# Ensure key indexes
try:
    db.news_articles.create_index('id', unique=True)
    db.news_articles.create_index('source_id')
    db.news_articles.create_index('published_at')
    db.news_articles.create_index('entities_mentioned')
    db.news_sources.create_index('id', unique=True)
    db.news_sources.create_index('is_active')
    db.deep_projects.create_index([('id', 1)], unique=True)
    db.deep_unlocks.create_index([('id', 1)], unique=True)
    db.deep_persons.create_index([('id', 1)], unique=True)
    db.deep_funds.create_index([('id', 1)], unique=True)
    db.deep_funding_rounds.create_index([('id', 1)], unique=True)
    print('  ✓ indexes ready')
except Exception as e:
    print(f'  ! index warning: {e}')
"
  
  # 4b) News sources seed (если коллекция пуста)
  echo "→ Checking news_sources seed..."
  python -c "
from pymongo import MongoClient
import os, sys
client = MongoClient(os.environ.get('MONGO_URL'))
db = client[os.environ.get('DB_NAME', 'fomo_mobile')]
n = db.news_sources.count_documents({})
print(f'  news_sources: {n}')
sys.exit(0 if n >= 100 else 1)
" || warn "news_sources < 100. Запустите scripts/seed_news_sources.py если есть."
  
  # 4c) RSS pipeline (один прогон)
  echo "→ Running one RSS pipeline cycle (это даёт ~30s)..."
  timeout 90 python scripts/run_rss_pipeline.py 2>&1 | grep -E "INGESTION|new=|articles after|sources_ok|SUMMARY" | tail -10
  
  # 4d) Deep parser cycle (один прогон)
  echo "→ Running one deep_parser cycle (это даёт ~60s)..."
  timeout 120 python -c "
import asyncio
from services.deep_parser import run_cycle
result = asyncio.run(run_cycle(cryptorank_limit=20, icodrops_limit=15, dropstab_limit=30, funds_limit=15, cmc_limit=20, concurrency=4))
print(f'  deep_parser: {result}')
" 2>&1 | tail -3
  
  cd ..
else
  warn "Skipping seed (--skip-seed)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5) VERIFY
# ─────────────────────────────────────────────────────────────────────────────
hdr "5. VERIFICATION"

BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
check() {
  local name="$1"; local url="$2"; local check_field="$3"
  local body=$(curl -s --max-time 10 "$url" 2>/dev/null)
  if [ -z "$body" ]; then
    err "$name → no response from $url"
    return 1
  fi
  if echo "$body" | python -c "import sys, json; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)" 2>/dev/null; then
    if [ -n "$check_field" ]; then
      local val=$(echo "$body" | python -c "import sys,json; d=json.load(sys.stdin); print($check_field)" 2>/dev/null)
      ok "$name → ok=true, $check_field=$val"
    else
      ok "$name → ok=true"
    fi
  else
    err "$name → ok=false or invalid: $(echo $body | head -c 200)"
  fi
}

check "Backend health"        "$BACKEND_URL/api/" ""
check "/api/deep/stats"       "$BACKEND_URL/api/deep/stats" "d['counts']['deep_projects']"
check "/api/deep/unlocks"     "$BACKEND_URL/api/deep/unlocks?limit=5" "d['count']"
check "/api/deep/funds"       "$BACKEND_URL/api/deep/funds?limit=5" "d['count']"
check "/api/deep/persons"     "$BACKEND_URL/api/deep/persons?limit=5" "d['count']"
check "/api/news/feed"        "$BACKEND_URL/api/news/feed?limit=5" "len(d.get('data',{}).get('clusters',[]))"
check "/api/backers"          "$BACKEND_URL/api/backers?limit=3" "len(d.get('bakers',[]))"

# Mongo summary
hdr "6. DB SUMMARY (fomo_mobile)"
python -c "
from pymongo import MongoClient
import os
client = MongoClient(os.environ.get('MONGO_URL'))
db = client[os.environ.get('DB_NAME', 'fomo_mobile')]
for col in ['news_articles', 'news_sources', 'sentiment_events',
            'deep_projects', 'deep_funding_rounds', 'deep_persons',
            'deep_unlocks', 'deep_funds', 'deep_project_events',
            'mbrain_verdicts', 'users']:
    try:
        cnt = db[col].count_documents({})
        active = ''
        if col == 'news_sources':
            active = f' (active: {db[col].count_documents({\"is_active\": True})})'
        print(f'  {col:<28}: {cnt}{active}')
    except Exception as e:
        print(f'  {col:<28}: ERR {e}')
"

hdr "DONE ✓"
echo "→ Web UI:   откройте preview URL"
echo "→ Backend:  $BACKEND_URL/api/"
echo "→ Logs:     tail -f /var/log/supervisor/backend.*.log"
echo "→ Sentiment refresh:  bash /app/scripts/run_sentiment.sh"

# ─────────────────────────────────────────────────────────────────────────────
# 7) FRACTAL & META BRAIN — cold-boot extension
# ─────────────────────────────────────────────────────────────────────────────
hdr "7. FRACTAL & META BRAIN"
if [ "$VERIFY_ONLY" = 1 ]; then
  bash /app/scripts/cold_boot_fractal.sh --verify-only || warn "Fractal verify reported issues"
else
  if [ "$SKIP_SEED" = 1 ]; then
    bash /app/scripts/cold_boot_fractal.sh --no-backfill || warn "Fractal cold-boot returned non-zero"
  else
    bash /app/scripts/cold_boot_fractal.sh || warn "Fractal cold-boot returned non-zero"
  fi
fi

echo ""
echo "→ Fractal docs:        cat /app/FRACTAL_API.md"
echo "→ Fractal deployment:  cat /app/FRACTAL_DEPLOYMENT.md"

# ─────────────────────────────────────────────────────────────────────────────
# 8) TECH ANALYSIS — cold-boot extension
# ─────────────────────────────────────────────────────────────────────────────
hdr "8. TECH ANALYSIS"
bash /app/scripts/cold_boot_ta.sh || warn "TA cold-boot returned non-zero"

echo ""
echo "→ TA docs:             cat /app/TA_API.md"

