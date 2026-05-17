# DEPENDENCIES.md — Полный список зависимостей FOMO OS

> Состояние: 2026-05-17. Все версии указаны как они находятся в `requirements.txt` / `package.json` на момент фиксации.

## Содержание
- [1. Backend (Python, FastAPI)](#1-backend-python-fastapi)
- [2. Frontend (React, CRA)](#2-frontend-react-cra)
- [3. Mobile (Expo)](#3-mobile-expo)
- [4. Browser Extension](#4-browser-extension)
- [5. Внешние сервисы](#5-внешние-сервисы)
- [6. Системные процессы (supervisor)](#6-системные-процессы-supervisor)

---

## 1. Backend (Python, FastAPI)

Файл: [`backend/requirements.txt`](./backend/requirements.txt) (~310 пакетов всего, ниже — production-critical)

### Web-framework и сериализация
| Пакет | Версия | Назначение |
|---|---|---|
| `fastapi` | 0.110.1 | HTTP-API сервер |
| `uvicorn` | latest | ASGI runner |
| `pydantic` | 2.x | Validation/serialization |
| `python-multipart` | latest | multipart/form-data |
| `email-validator` | 2.3.0 | email field validation |

### MongoDB
| Пакет | Версия | Назначение |
|---|---|---|
| `pymongo` | 4.x | sync клиент |
| `motor` | latest | async клиент |
| `fastuuid` | 0.14.0 | быстрая генерация UUID |

### Биржи и финансовые данные (M1 TA, M4 Exchange)
| Пакет | Версия | Назначение |
|---|---|---|
| `ccxt` | 4.5.53 | универсальный клиент 100+ бирж |
| `aiohttp` | 3.13.3 | async HTTP для биржевых WS |
| `websockets` | latest | live order-flow streams |
| `pandas`, `numpy`, `scipy` | latest | тех. индикаторы и fractal similarity |

### News / RSS (M5.1)
| Пакет | Версия | Назначение |
|---|---|---|
| `feedparser` | 6.0.12 | RSS/Atom парсинг |
| `httpx` | latest | HTTP-клиент для скрейпинга |
| `beautifulsoup4` | 4.14.3 | HTML parsing для deep_parser |
| `curl_cffi` | 0.13.0 | TLS-fingerprint emulation (anti-bot) |
| `fake-useragent` | 2.2.0 | UA rotation |

### Twitter (M5.2)
| Пакет | Версия | Назначение |
|---|---|---|
| `playwright` | latest | L2 fallback (если расширение недоступно) |
| `twscrape` *(опц.)* | latest | L1 ingestion |

### Auth & Security
| Пакет | Версия | Назначение |
|---|---|---|
| `google-auth`, `google-auth-oauthlib` | latest | Google OAuth ID token verification |
| `google-api-core` | 2.29.0 | Google APIs core |
| `python-jose[cryptography]` | latest | JWT session tokens |
| `bcrypt` | 4.1.3 | password hashing |
| `cryptography` | 46.0.4 | TLS + JWT crypto |

### AI / LLM (Sentiment Neural)
| Пакет | Версия | Назначение |
|---|---|---|
| `emergentintegrations` | 0.1.0 | универсальный wrapper над OpenAI/Anthropic/Gemini через `EMERGENT_LLM_KEY` |
| `google-ai-generativelanguage` | 0.6.15 | Gemini ML |

### Schedulers / Background loops
| Пакет | Версия | Назначение |
|---|---|---|
| `APScheduler` | 3.11.2 | периодические задачи (news_substrate, deep_parser cycles) |

### Storage / S3
| Пакет | Версия | Назначение |
|---|---|---|
| `boto3` | 1.42.42 | S3 (для media uploads если потребуется) |
| `aiosqlite` | 0.22.1 | локальная сессионная БД (`accounts.db`) |

### Crypto (on-chain интеграции)
| Пакет | Версия | Назначение |
|---|---|---|
| `coincurve` | 21.0.0 | ECDSA signing для wallet operations |
| `ecdsa` | 0.19.1 | сигнатуры |

### Dev / Lint
- `black`, `flake8`, `ruff` — code style.

### Установка
```bash
cd /app/backend
pip install -r requirements.txt
```

---

## 2. Frontend (React, CRA)

Файл: [`frontend/package.json`](./frontend/package.json) (66 runtime + 18 dev зависимостей).

### Core
| Пакет | Версия | Назначение |
|---|---|---|
| `react`, `react-dom` | ^19.0.0 | UI framework |
| `react-router-dom` | ^7.5.1 | SPA routing |
| `react-scripts` | 5.0.1 | CRA build |
| `@craco/craco` | ^7.1.0 | CRA config override |
| `typescript` | ^5.9.3 | TS support |
| `zustand` | ^5.0.11 | state management |
| `react-hook-form` + `@hookform/resolvers` + `zod` | latest | формы и валидация |

### UI Library — Shadcn (на базе Radix)
30+ Radix UI primitives: `@radix-ui/react-{accordion,dialog,dropdown-menu,select,tabs,toast,tooltip,...}` — все они обёрнуты в локальные компоненты в `frontend/src/components/ui/`.

| Пакет | Назначение |
|---|---|
| `tailwindcss` ^3.4 + `tailwindcss-animate` + `tailwind-merge` | styling |
| `class-variance-authority`, `clsx` | conditional class composition |
| `lucide-react` ^0.562 | иконки (≈ 1000+ icons) |
| `sonner` ^2.0 | toasts |
| `cmdk` | command palette |
| `vaul` | drawers |
| `framer-motion` ^12 | animations |
| `next-themes` | dark/light mode |
| `styled-components` ^6.4 | styled CSS-in-JS |

### Charts & Visualization
| Пакет | Назначение |
|---|---|
| `recharts` ^3.7 | основные графики |
| `lightweight-charts` ^5.1 | trading-style candlestick charts |
| `echarts` + `echarts-for-react` | rich charts |
| `@nivo/bar`, `@nivo/core` | специальные bar charts |
| `d3-force`, `react-force-graph-2d` | network graphs (Sentiment Graph tab) |
| `three` ^0.182 | 3D visualization |
| `d3-scale`, `d3-shape` | низкоуровневый D3 |

### Payments
| Пакет | Назначение |
|---|---|
| `@stripe/react-stripe-js`, `@stripe/stripe-js` | Stripe checkout |

### Прочее
| Пакет | Назначение |
|---|---|
| `axios` ^1.8 | HTTP (часть вызовов; основная масса через `fetch`) |
| `date-fns` ^4.1 | date utils |
| `html2canvas` ^1.4 | export-to-image |
| `react-markdown` ^10.1 | markdown rendering |
| `embla-carousel-react` | carousels |
| `input-otp` | OTP-поля |

### Установка
```bash
cd /app/frontend
yarn install  # NEVER use npm
```

---

## 3. Mobile (Expo)

Файл: [`mobile/package.json`](./mobile/package.json) (~42 deps).

### Core Expo Stack
| Пакет | Версия | Назначение |
|---|---|---|
| `expo` | ~54.0.34 | framework |
| `expo-router` | ~6.0.22 | file-based routing |
| `react-native` | ~0.81.x | UI |
| `@react-navigation/native`, `@react-navigation/native-stack`, `@react-navigation/bottom-tabs` | ^7.x | navigation |

### Auth (Google + Apple)
| Пакет | Назначение |
|---|---|
| `expo-auth-session` ~7.0.11 | OAuth flow |
| `expo-crypto` ~15.0.9 | для challenge/verifier |
| `expo-secure-store` ~15.0.8 | хранение tokens |

### Storage / Network
| Пакет | Назначение |
|---|---|
| `@react-native-async-storage/async-storage` 2.2.0 | persistence |
| `axios` ^1.15 | HTTP |

### UI
| Пакет | Назначение |
|---|---|
| `@expo/vector-icons` ^15.0 | иконки |
| `expo-blur`, `expo-image`, `expo-haptics` | визуал |

### Build deployment
Mobile build выкладывается через web-build на `/api/app/*` (rewrite mobile HTML делается в `backend/server.py`).

### Установка
```bash
cd /app/mobile
yarn install
yarn export -p web  # генерит /app/mobile/dist
```

---

## 4. Browser Extension

Файл: [`backend/admin_build/fomo_extension_v1.3.0/manifest.json`](./backend/admin_build/fomo_extension_v1.3.0/manifest.json)

- **Manifest version**: 3
- **Minimum Chrome**: 116
- **Permissions**: `cookies`, `storage`
- **Host permissions**: `https://twitter.com/*`, `https://x.com/*`
- **Background**: `background.js` (service worker, type=module)

Никаких внешних JS-библиотек — чистый vanilla JS (`twitter-fetcher.js`, `cookie-quality-checker.js`, `popup.js`, `backend-error-mapper.js`).

См. [`EXTENSION.md`](./EXTENSION.md) для деталей.

---

## 5. Внешние сервисы

| Сервис | Назначение | Требуемые ключи |
|---|---|---|
| **MongoDB** | Основная БД (`fomo_mobile`) | `MONGO_URL` |
| **Google Identity Services** | OAuth login | `GOOGLE_CLIENT_ID` |
| **EmergentLLM gateway** | OpenAI/Anthropic/Gemini text+image gen | `EMERGENT_LLM_KEY` |
| **Stripe** *(опц.)* | Subscriptions | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` |
| **Binance / Bybit / OKX** | Live market data | публичные REST/WS, ключи не нужны для read |
| **CoinGecko** | Цены, market caps | публичный API (rate-limited) |
| **CryptoCompare News API** | Новости | публичный API |
| **Fear & Greed Index** (alternative.me) | Sentiment overlay | публичный JSON |
| **RSS-сайты** (119 source-feeds) | Новостной substrate | публичные RSS |
| **DropsTab / CryptoRank / ICODrops / CoinMarketCap** | Deep parser SSR scrape | публичные HTML страницы |
| **Twitter/X** | Через расширение из браузера юзера | сессионные cookies юзера |

---

## 6. Системные процессы (supervisor)

`/etc/supervisor/conf.d/*.conf` (или эквивалент в платформе):

| Процесс | Команда (пример) | Назначение |
|---|---|---|
| `backend` | `uvicorn server:app --host 0.0.0.0 --port 8001 --reload` | FastAPI |
| `frontend` | `yarn start` (CRA dev) | React :3000 |
| `mongodb` | `mongod` | локальная БД |
| `news_substrate` | `python -m services.news_substrate_loop` | непрерывный RSS/news loop |
| `code-server` | (по умолчанию stopped) | опционально для editor |
| `nginx-code-proxy` | nginx | прокси для code-server |

Управление:
```bash
supervisorctl status
supervisorctl restart backend frontend news_substrate
```

---

## Установка с нуля (clean machine)

```bash
# Python
cd /app/backend && pip install -r requirements.txt

# Frontend
cd /app/frontend && yarn install

# Mobile (опц.)
cd /app/mobile && yarn install && yarn export -p web

# Запуск
supervisorctl restart backend frontend news_substrate

# Verify + seed
bash /app/scripts/bootstrap.sh --skip-deps
```
