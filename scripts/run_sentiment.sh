#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# FOMO OS — Sentiment refresh
# ─────────────────────────────────────────────────────────────────────────────
# Полный прогон Sentiment-логики:
#   1) RSS pipeline (119 источников) → news_articles + sentiment_events
#   2) Deep parser cycle → deep_projects/funds/persons/unlocks (DropsTab,
#      CryptoRank, ICODrops, CoinMarketCap)
#   3) Twitter sentiment step (если есть свежие cookies через Extension)
#
# Usage:
#   bash /app/scripts/run_sentiment.sh                # полный прогон
#   bash /app/scripts/run_sentiment.sh --rss-only     # только RSS
#   bash /app/scripts/run_sentiment.sh --deep-only    # только deep_parser
#   bash /app/scripts/run_sentiment.sh --twitter-only # только Twitter
# ─────────────────────────────────────────────────────────────────────────────
set -e

GRN='\033[0;32m'; YLW='\033[1;33m'; BLU='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GRN}✓${NC} $*"; }
warn() { echo -e "${YLW}⚠${NC} $*"; }
hdr()  { echo -e "\n${BLU}══ $* ══${NC}"; }
err()  { echo -e "${RED}✗${NC} $*"; }

RSS=1; DEEP=1; TWITTER=1
for arg in "$@"; do
  case "$arg" in
    --rss-only)     RSS=1; DEEP=0; TWITTER=0 ;;
    --deep-only)    RSS=0; DEEP=1; TWITTER=0 ;;
    --twitter-only) RSS=0; DEEP=0; TWITTER=1 ;;
    *) warn "Unknown flag: $arg" ;;
  esac
done

cd /app/backend
set -a
. ./.env
set +a
export MONGO_URL DB_NAME

# ─── 1. RSS ──────────────────────────────────────────────────────────────────
if [ "$RSS" -eq 1 ]; then
  hdr "1. RSS Pipeline (119 sources)"
  if timeout 180 python scripts/run_rss_pipeline.py 2>&1 | tee /tmp/rss_pipeline.log | grep -E "INGESTION|new=|sources_ok|sources_empty|articles after" | tail -15; then
    ok "RSS pipeline finished"
  else
    warn "RSS pipeline timeout/error (см. /tmp/rss_pipeline.log)"
  fi
fi

# ─── 2. Deep Parser ──────────────────────────────────────────────────────────
if [ "$DEEP" -eq 1 ]; then
  hdr "2. Deep Parser (DropsTab + CryptoRank + ICODrops + CoinMarketCap)"
  timeout 180 python -c "
import asyncio, logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
from services.deep_parser import run_cycle
result = asyncio.run(run_cycle(
    cryptorank_limit=30,
    icodrops_limit=20,
    dropstab_limit=40,
    funds_limit=20,
    cmc_limit=20,
    concurrency=4,
))
print()
print('═══════════════════════════════════════════')
print('  DEEP PARSER RESULT:')
print('═══════════════════════════════════════════')
for k, v in result.items():
    if k != 'errors':
        print(f'  {k:<15}: {v}')
errs = result.get('errors', [])
if errs:
    print(f'  errors ({len(errs)}):')
    for e in errs[:10]:
        print(f'    {e}')
" 2>&1 | tee /tmp/deep_parser.log | tail -25 || warn "deep_parser timeout"
fi

# ─── 3. Twitter (если есть скрипт + cookies) ─────────────────────────────────
if [ "$TWITTER" -eq 1 ]; then
  hdr "3. Twitter Sentiment Step"
  if [ -f scripts/twitter_sentiment_step.py ]; then
    timeout 120 python scripts/twitter_sentiment_step.py 2>&1 | tee /tmp/twitter_step.log | tail -15 || warn "twitter step issue (cookies?)"
  else
    warn "scripts/twitter_sentiment_step.py не найден — пропуск"
  fi
fi

# ─── Final summary ──────────────────────────────────────────────────────────
hdr "DB SUMMARY"
python -c "
from pymongo import MongoClient
import os
client = MongoClient(os.environ.get('MONGO_URL'))
db = client[os.environ.get('DB_NAME', 'fomo_mobile')]
def row(name, q={}):
    print(f'  {name:<28}: {db[name].count_documents(q)}')
row('news_articles')
row('news_sources')
print(f'  news_sources (active)       : {db.news_sources.count_documents({\"is_active\": True})}')
row('sentiment_events')
row('deep_projects')
row('deep_funding_rounds')
row('deep_persons')
row('deep_unlocks')
print(f'    └─ source=dropstab        : {db.deep_unlocks.count_documents({\"source\": \"dropstab\"})}')
print(f'    └─ source=coinmarketcap   : {db.deep_unlocks.count_documents({\"source\": \"coinmarketcap\"})}')
print(f'    └─ source=cryptorank      : {db.deep_unlocks.count_documents({\"source\": \"cryptorank\"})}')
row('deep_funds')
row('twitter_tweets')
row('twitter_accounts')
"

ok "Sentiment refresh completed"
echo "→ Логи: /tmp/rss_pipeline.log, /tmp/deep_parser.log, /tmp/twitter_step.log"
