# FOMO OS

> Web3 analytics platform with **MetaBrain 5-module consensus engine**.  
> Single-repo, production-ready, без внешних submodule зависимостей.

---

## 🚀 Quick start

```bash
# Полное idempotent-развёртывание (env-check → deps → seed → verify)
bash /app/scripts/bootstrap.sh

# Обновить только Sentiment (RSS + Deep parser + Twitter)
bash /app/scripts/run_sentiment.sh
```

---

## 📚 Документация (вся в корне репозитория)

| Документ | Что внутри |
|---|---|
| **[PROJECT.md](./PROJECT.md)** ⭐ | **Главный документ**: архитектура, 5 модулей, Sentiment, Google auth, Chrome Extension, deployment, validation checklist |
| **[MODULES.md](./MODULES.md)** | Детальное описание **5 модулей MetaBrain** с диаграммами зависимостей, файлами и endpoints |
| **[MOBILE_AND_MINIAPP.md](./MOBILE_AND_MINIAPP.md)** ⭐ | **Mobile (Expo Android/iOS) + Telegram MiniApp**: структура, routing, auth flow, 57 MiniApp endpoints, связь Web↔Mobile↔MiniApp, acceptance checklist |
| **[CODE_DIAGRAM.md](./CODE_DIAGRAM.md)** | Визуальные диаграммы: system, backend tree, frontend tree, data flow для Sentiment, Extension flow, router order |
| **[DEPENDENCIES.md](./DEPENDENCIES.md)** | Полный список зависимостей: Python (FastAPI), Node (React 19 + Shadcn), Expo, browser extension, внешние сервисы |
| **[API.md](./API.md)** | Полная карта endpoints: Auth, MetaBrain, Sentiment, Deep parser, Twitter+Extension, Mobile, Telegram, Billing, Admin |
| **[EXTENSION.md](./EXTENSION.md)** | Chrome Extension "FOMO X Connect" — установка, поток данных (indirect method), backend endpoints |
| **[SENTIMENT_API.md](./SENTIMENT_API.md)** | Подробное описание Sentiment API endpoints |
| **[TWITTER_INSTALL.md](./TWITTER_INSTALL.md)** | Гайд по установке и настройке Twitter parsing |
| **[TELEGRAM_INTEL.md](./TELEGRAM_INTEL.md)** | Telegram intelligence module |
| **[PRD.md](./PRD.md)** | Product Requirements Document |
| **[plan.md](./plan.md)** | Текущее состояние / план разработки |

> Все исторические audit-логи, handoff-документы и snapshot-отчёты перемещены в `/app/_archive_2026-05/` и не используются для принятия решений.

---

## 🏗 Архитектура (краткое)

```
USERS (Web / Mobile / TG MiniApp / Chrome Ext)
  │
  ▼  HTTPS  /api/*
┌─────────────────────────────────────────────┐
│  FastAPI Backend (port 8001)                │
│  ──────────────────────                     │
│   MetaBrain Consensus                       │
│   ├ M1 TechAnalysis (CCXT OHLC)             │
│   ├ M2 Fractal (native engine)              │
│   ├ M3 OnChain (per-asset)                  │
│   ├ M4 Exchange (Binance/Bybit/OKX live)    │
│   └ M5 Sentiment (RSS×119 + Twitter +       │
│       Deep parser DropsTab/CryptoRank/       │
│       ICODrops/CMC + Fear&Greed)             │
└────────────────┬────────────────────────────┘
                 │
                 ▼
        MongoDB (fomo_mobile)
                 ▲
                 │
   Supervisor:  backend / frontend / mongodb / news_substrate
```

Полная диаграмма с module-tree → см. [`CODE_DIAGRAM.md`](./CODE_DIAGRAM.md).

---

## 📦 Структура корня

```
/app/
├── README.md                 ← ЭТОТ ФАЙЛ (главное оглавление)
├── PROJECT.md                ← полное описание проекта
├── MODULES.md                ← 5 модулей в деталях
├── MOBILE_AND_MINIAPP.md     ← Mobile (Expo) + Telegram MiniApp
├── CODE_DIAGRAM.md           ← диаграммы кода и data-flow
├── DEPENDENCIES.md           ← все зависимости
├── API.md                    ← карта endpoints
├── EXTENSION.md              ← Chrome Extension
├── SENTIMENT_API.md          ← Sentiment API docs
├── TWITTER_INSTALL.md        ← Twitter setup guide
├── TELEGRAM_INTEL.md         ← Telegram module
├── PRD.md                    ← Product Requirements
├── plan.md                   ← текущий план
│
├── scripts/
│   ├── bootstrap.sh          ← всё-в-одном развёртывание
│   └── run_sentiment.sh      ← Sentiment refresh
│
├── backend/                  ← FastAPI (port 8001)
├── frontend/                 ← React 19 + Shadcn (port 3000)
├── mobile/                   ← Expo build
│
└── _archive_2026-05/         ← старые аудиты (не трогать)
```

---

## 🔧 Управление сервисами

```bash
# Статус
supervisorctl status

# Перезапуск
supervisorctl restart backend frontend news_substrate

# Логи
tail -f /var/log/supervisor/backend.*.log
tail -f /var/log/supervisor/frontend.*.log
```

---

## ✅ Live data summary (на момент фиксации)

| Коллекция | Документов |
|---|---|
| news_articles | 3087 |
| news_sources (active) | 119 |
| sentiment_events | 4483 |
| deep_projects | 106 |
| deep_funding_rounds | 386 |
| deep_persons | 899 |
| deep_unlocks | 26 (17 CMC + 9 DropsTab vesting) |
| deep_funds | 20 |
| deep_project_events | 655 |

---

## 🌐 Внешние ключи (`backend/.env`)

| Ключ | Назначение | Обязателен |
|---|---|---|
| `MONGO_URL` | MongoDB | да |
| `DB_NAME` | имя БД (`fomo_mobile`) | да |
| `EMERGENT_LLM_KEY` | OpenAI/Anthropic/Gemini gateway | для AI features |
| `GOOGLE_CLIENT_ID` | Google OAuth audience | для Google login |
| `DEEP_PARSER_ENABLED` | true/false | опц. (default true) |
| `DEEP_PARSER_INTERVAL_SEC` | секунды между циклами | опц. (default 21600) |

---

## 🛠 Тестирование

```bash
BACKEND="http://localhost:8001"
curl -s "$BACKEND/api/deep/stats" | jq
curl -s "$BACKEND/api/news/feed?limit=5" | jq
curl -s "$BACKEND/api/backers?limit=3" | jq
curl -s "$BACKEND/api/onchain/runtime/DOGE" | jq
```

Все endpoint'ы и примеры — см. [`API.md`](./API.md).

---

## 📜 Лицензия и контакты

Внутренний проект. Все права у владельца. Документация написана для разработчиков и AI-агентов, продолжающих работу над платформой.
