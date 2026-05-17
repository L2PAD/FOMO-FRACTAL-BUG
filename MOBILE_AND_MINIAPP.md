# MOBILE_AND_MINIAPP.md — Expo Mobile & Telegram MiniApp logic

> Production-state на 2026-05-17. Описывает три клиента FOMO OS (Web / Mobile / Telegram MiniApp) и их связь с backend, чтобы при дальнейшей разработке логика не потерялась.

---

## 1. Три клиента — одно backend ядро

```
                ┌──────────────────────────────────────────────┐
                │              FastAPI Backend                 │
                │              port 8001 / /api/*              │
                │                                              │
                │  ── Shared core: MetaBrain + MongoDB ──      │
                │                                              │
                └──────┬──────────────┬──────────────┬─────────┘
                       │              │              │
        ┌──────────────┴──┐  ┌────────┴───────┐  ┌───┴──────────────┐
        │   WEB Client    │  │  MOBILE (Expo) │  │  TG MiniApp      │
        │   React 19 +    │  │  iOS / Android │  │  WebApp inside   │
        │   Shadcn UI     │  │  + Web export  │  │  Telegram        │
        │   port 3000     │  │  /api/app/*    │  │  /miniapp/*      │
        └─────────────────┘  └────────────────┘  └──────────────────┘

           Auth: Google OAuth        Google + Apple SignIn    Telegram WebApp initData
                 + Email             + Secure Store           HMAC verification
```

Все три клиента работают через **один и тот же FastAPI backend**. Различаются только:
- путём сервинга UI (`localhost:3000` vs `/api/app/*` vs `/api/miniapp/*`),
- механизмом auth (Google ID-token vs Apple/Google + Secure Store vs Telegram initData HMAC),
- набором доступных endpoint'ов (mobile/miniapp используют SPA-friendly variants).

---

## 2. Mobile App (Expo)

### 2.1 Расположение
```
/app/mobile/
├── app.json                    ← Expo конфиг
├── package.json                ← 42 deps (Expo Router 6, RN 0.81, Reanimated)
├── tsconfig.json
├── metro.config.js
├── start-web.sh
│
├── app/                        ← Expo Router file-based routing
│   ├── _layout.tsx             │ Root layout (auth state, navigation)
│   ├── +html.tsx               │ Web HTML wrapper
│   ├── index.tsx               │ Главный экран (Alpha equivalent)
│   ├── exchange.tsx            │ Exchange tab
│   ├── pricing.tsx             │ Подписка
│   ├── info.tsx                │ About / settings
│   ├── admin/                  │ Admin operator panel
│   ├── attribution/            │ Attribution dashboard
│   ├── legal/                  │ ToS / Privacy
│   ├── operator/               │ Broker operator UI (currently noop)
│   ├── positions/              │ Paper positions
│   ├── privacy/                │
│   ├── ref/                    │ Referral
│   ├── snapshot/               │ Snapshot шеринг
│   └── verdicts/               │ MetaBrain verdicts list
│
├── src/
│   ├── admin/                  │ Admin-specific screens
│   ├── components/             │ Переиспользуемые RN компоненты
│   ├── core/                   │ Core utilities (API client, theme)
│   ├── hooks/                  │ React hooks
│   ├── modules/                │ Feature modules
│   ├── services/               │ API services
│   ├── stores/                 │ Zustand stores (mobile)
│   ├── types/                  │ TS types
│   ├── utils/                  │
│   └── widgets/                │
│
├── assets/                     ← иконки, шрифты, splash
├── public/                     ← web export public
└── scripts/                    ← build helpers
```

### 2.2 Routing (Expo Router 6)
File-based: `app/exchange.tsx` → `/exchange`, `app/admin/index.tsx` → `/admin`, и т.д.

Главный layout (`app/_layout.tsx`) определяет:
- Theme (light/dark),
- Auth state (через `expo-secure-store`),
- Bottom tabs / stack navigation.

### 2.3 Auth flow (Mobile)
```
1. User tap "Login with Google" (или Apple)
2. expo-auth-session → Google Identity Services → возврат ID-token
3. POST /api/mobile/auth/google body={idToken}
4. Backend validates token (google.oauth2.id_token), find_or_create user
5. JWT session token → expo-secure-store
6. Все последующие /api/* запросы с Authorization: Bearer <jwt>
```

Source: `routes/mobile_auth.py:google_auth`, см. [API.md](./API.md) → "Auth & User".

### 2.4 Web export (для serve через backend)
```bash
cd /app/mobile
yarn export -p web      # генерирует /app/mobile/dist/
```

Backend (`server.py:7667-7711`) монтирует `/app/mobile/dist`:
- `/api/app/_expo/*` → static Expo bundles
- `/api/app/assets/*`, `/api/app/static/*` → assets
- `/api/app/{path:path}` → SPA fallback (рерайтит HTML, чтобы все `/...` ссылки стали `/api/app/...`)

То есть Mobile-сборка доступна **из браузера** по адресу `<preview-url>/api/app/` — это удобно для preview/demo, не нужно ставить нативное приложение.

### 2.5 Native build (Android / iOS)
- Android APK: `eas build -p android`
- iOS: `eas build -p ios`
- Конфиг в `mobile/app.json`.

### 2.6 Ключевые экраны
| Экран | Файл | Что делает |
|---|---|---|
| Alpha | `app/index.tsx` | Главная: верделикт MetaBrain по активу + chart |
| Exchange | `app/exchange.tsx` | M4 Exchange tab |
| Verdicts | `app/verdicts/` | История verdict'ов |
| Positions | `app/positions/` | Paper-trade positions |
| Operator | `app/operator/broker.tsx` | Broker operator panel (noop) |
| Attribution | `app/attribution/` | Module attribution charts |
| Admin | `app/admin/` | Admin-only screens (требует admin auth) |
| Pricing | `app/pricing.tsx` | Subscription tiers |
| Info | `app/info.tsx` | About / Settings |

### 2.7 Зависимости (Mobile-specific)
Полный список — см. [DEPENDENCIES.md §3](./DEPENDENCIES.md). Ключевые:
- `expo`, `expo-router`, `react-native`
- `@react-navigation/native` + `native-stack` + `bottom-tabs`
- `expo-auth-session`, `expo-secure-store`, `expo-crypto` (для OAuth)
- `@react-native-async-storage/async-storage`
- `axios`

---

## 3. Telegram MiniApp

### 3.1 Где живёт код
Backend-driven (НЕ отдельный фронт-проект). Логика:
- **API endpoints**: 57 routes в `server.py` + `routes/miniapp_lite.py` (197 KB!)
- **Business logic**: `/app/backend/miniapp/` модуль
- **Static HTML/JS** (lite version): сервится через `/api/miniapp/lite-url`

### 3.2 Структура `backend/miniapp/`
```
backend/miniapp/
├── __init__.py
├── core_builder.py             ← главный билдер home screen
├── home_builder.py             ← lite home (быстрая версия)
├── profile_builder.py          ← user profile screen
├── edge_builder.py             ← Edge intelligence screen
├── edge_priority.py            │
├── edge_alerts.py              │
├── user_state.py               ← state management (Google linking и т.д.)
├── ab_testing.py               ← A/B test variants
├── alert_boost.py              ← alert system
├── accuracy_audit.py           ← accuracy tracking
├── billing_bridge.py           ← Stripe bridge для MiniApp
├── bot_setup.py                ← Telegram bot configuration
├── polymarket_ingestion.py     ← Polymarket integration
└── scheduler.py                ← Background scheduler
```

### 3.3 Endpoints (главные, всего 57)

#### Core UI endpoints
| Endpoint | Назначение |
|---|---|
| `GET /api/miniapp/core` | Главная страница MiniApp (HTML + JS) |
| `GET /api/miniapp/lite-url` | URL lite-версии |
| `GET /api/miniapp/lite/favicon.ico`, `/logo.png` | Static assets |
| `GET /api/miniapp/home` | Home shell с данными |
| `GET /api/miniapp/feed` | News feed для MiniApp |
| `GET /api/miniapp/edge` | Edge opportunities |
| `GET /api/miniapp/edge/v2` | Edge v2 (новый формат) |
| `GET /api/miniapp/profile` | Профиль пользователя |
| `GET /api/miniapp/search` | Search |
| `GET /api/miniapp/polymarket` | Polymarket bridge |

#### Auth & state
| Endpoint | Назначение |
|---|---|
| `POST /api/miniapp/sync-telegram-user` | Sync user info после Telegram WebApp init |
| `POST /api/miniapp/user/link-google` | Линковка Google email с Telegram identity |
| `POST /api/miniapp/user/unlink-google` | Отвязка Google |
| `GET  /api/miniapp/user/state` | Текущее состояние user |
| `POST /api/miniapp/webhook` | Telegram webhook receiver |

#### Settings & favorites
| Endpoint | Назначение |
|---|---|
| `POST /api/miniapp/settings` | Update user settings |
| `POST /api/miniapp/favorites/add` / `remove` | Manage favorites |
| `POST /api/miniapp/promo/apply` | Apply promo code |

#### Billing (Stripe через MiniApp)
| Endpoint | Назначение |
|---|---|
| `GET  /api/miniapp/billing/plans` | Доступные планы |
| `GET  /api/miniapp/billing/status` | Текущий план |
| `POST /api/miniapp/billing/checkout` | Создать checkout session |
| `POST /api/miniapp/billing/portal` | Stripe portal link |
| `GET  /api/miniapp/billing/verify/{session_id}` | Verify checkout |

#### Analytics & A/B testing
| Endpoint | Назначение |
|---|---|
| `GET  /api/miniapp/ab/stats` | A/B test stats |
| `POST /api/miniapp/ab/track` | Track A/B event |
| `GET  /api/miniapp/accuracy/audit` | Accuracy audit data |

#### Prediction & charts
| Endpoint | Назначение |
|---|---|
| `GET  /api/miniapp/prediction-chart` | Prediction chart data |
| `POST /api/miniapp/prediction/broadcast` | Broadcast prediction |
| `GET  /api/miniapp/prediction/shift-status` | Shift status |
| `GET  /api/miniapp/chart-series` | Chart series data |

#### Alerts & digests
| Endpoint | Назначение |
|---|---|
| `POST /api/miniapp/alerts/send` | Send alert |
| `POST /api/miniapp/digest/send` | Send daily digest |

#### Bot configuration
| Endpoint | Назначение |
|---|---|
| `POST /api/miniapp/bot/set-menu-lite` | Set Telegram bot menu (lite) |

### 3.4 Auth flow (Telegram MiniApp)
```
1. User открывает FOMO bot в Telegram → нажимает "Open App"
2. Telegram WebView грузит /api/miniapp/core
3. Telegram передаёт window.Telegram.WebApp.initData (HMAC-подписанный JSON)
4. Frontend JS вытаскивает initData → POST /api/miniapp/sync-telegram-user
5. Backend проверяет HMAC signature (через bot secret token)
6. find_or_create user в MongoDB по telegram_id
7. (опц.) пользователь нажимает "Link Google" → POST /api/miniapp/user/link-google
   с body {email, name} (получаемых через Telegram WebApp.requestContact?
   или через переход в браузер на Google OAuth → редирект обратно)
```

Источник: `routes/miniapp_lite.py`, `backend/miniapp/user_state.py:link_google_account`.

### 3.5 Admin endpoints для MiniApp
| Endpoint | Назначение |
|---|---|
| `GET /api/admin/miniapp/overview` | Общая статистика |
| `GET /api/admin/miniapp/users` | Список users |
| `GET /api/admin/miniapp/signals` | Sent signals |
| `GET /api/admin/miniapp/alerts` | Alerts history |
| `GET /api/admin/miniapp/billing` | Billing dashboard |
| `GET /api/admin/miniapp/edges` | Edge opportunities tracking |
| `GET /api/admin/miniapp/settings` | Admin settings |
| `PUT /api/admin/miniapp/settings` | Update admin settings |

### 3.6 Tests (важно)
`backend/tests/` содержит 10+ файлов **именно для MiniApp**:
- `test_miniapp_core.py`
- `test_miniapp_home_shell.py`
- `test_miniapp_v2_intelligence.py`
- `test_miniapp_event_tracking.py`
- `test_miniapp_admin_v2_money_dashboard.py`
- `test_miniapp_alerts_digest_edge_v2.py`
- `test_miniapp_priority_ab_testing.py`
- `test_miniapp_user_scheduler_edge.py`
- `test_miniapp_welcome_profile_webhook.py`

Это значит миниап **production-tested**. Запуск:
```bash
cd /app/backend && pytest tests/test_miniapp_*.py -v
```

---

## 4. Связь Web ↔ Mobile ↔ MiniApp

### 4.1 Shared accounts (cross-client identity)
Одна запись `users` в MongoDB может иметь:
```js
{
  _id: "u_abc123",
  email: "user@example.com",
  authProviders: {
    google:   true,    // ← пришёл через web или mobile Google
    email:    false,
    telegram: true     // ← залинкован Telegram identity
  },
  linkedApps: {
    web:     true,
    miniapp: true,
    mobile:  true
  },
  plan: "PRO",
  // ...
}
```

Один и тот же план `PRO` действует во всех трёх клиентах.

### 4.2 Cross-app linking
| Источник | Целевой | Endpoint | Что делает |
|---|---|---|---|
| Telegram MiniApp | Google account | `POST /api/miniapp/user/link-google` | Связывает Telegram_id ↔ Google email |
| Telegram MiniApp | Unlink | `POST /api/miniapp/user/unlink-google` | Удаляет привязку |
| Web → MiniApp | через email | Web auth + Telegram bot inline shares one user record | Авто-link если email совпадает |

### 4.3 Shared data layer
Все клиенты читают одну MongoDB `fomo_mobile`:
- `mbrain_verdicts` — одни и те же verdicts видны во всех клиентах,
- `news_articles`, `sentiment_events` — общие,
- `paper_positions` — позиции пользователя видны и в web, и в mobile.

### 4.4 Дифференциация по surface
В `auth_gate.py` есть параметр `surface`:
```
GET /api/auth/gate?surface=web_paywall
GET /api/auth/gate?surface=mobile_paywall
GET /api/auth/gate?surface=miniapp_paywall
```
Разные paywall-конфигурации возвращаются под разные клиенты (`linkedApps` поле в `users`).

### 4.5 Stripe billing (единая источник правды)
- Web: `/api/billing/checkout` → Stripe checkout session
- Mobile: то же самое + deep-link обратно через `expo-linking`
- MiniApp: `/api/miniapp/billing/checkout` → Stripe → `verify/{session_id}`

Все три ведут к одной записи `subscription` в `users.{subscription}`.

---

## 5. Browser Extension (Chrome) — четвёртый «клиент»

См. [EXTENSION.md](./EXTENSION.md). Расширение **не имеет своего UI** на FOMO домене, оно работает как мост Twitter → backend:
- Бежит в браузере пользователя
- Получает cookies к Twitter из живой сессии юзера
- Отправляет batch tweets/profiles в backend через `/api/v4/twitter/sessions/webhook` и `/api/v4/twitter/ingest`
- Это поднимает `twitter_tweets` и `twitter_accounts` коллекции, которые потом видят web/mobile/miniapp в Sentiment tabs.

---

## 6. Что НЕ должно деградировать (acceptance checklist)

Запустить после любых изменений в backend для проверки:

```bash
BACKEND="http://localhost:8001"

# Mobile (Expo web export)
curl -s -o /dev/null -w "Mobile /api/app/:           HTTP %{http_code}\n" "$BACKEND/api/app/"

# Telegram MiniApp
curl -s -o /dev/null -w "MiniApp /api/miniapp/core:  HTTP %{http_code}\n" "$BACKEND/api/miniapp/core"
curl -s -o /dev/null -w "MiniApp /api/miniapp/home:  HTTP %{http_code}\n" "$BACKEND/api/miniapp/home"
curl -s -o /dev/null -w "MiniApp /api/miniapp/feed:  HTTP %{http_code}\n" "$BACKEND/api/miniapp/feed"
curl -s -o /dev/null -w "MiniApp billing/plans:      HTTP %{http_code}\n" "$BACKEND/api/miniapp/billing/plans"

# Admin
curl -s -o /dev/null -w "Admin /api/admin/users:     HTTP %{http_code}\n" "$BACKEND/api/admin/users"
curl -s -o /dev/null -w "Admin /api/admin/core7:     HTTP %{http_code}\n" "$BACKEND/api/admin/core7"
curl -s -o /dev/null -w "Admin miniapp/overview:     HTTP %{http_code}\n" "$BACKEND/api/admin/miniapp/overview"

# Cross-app shared
curl -s -o /dev/null -w "Shared /api/users/me:       HTTP %{http_code}\n" "$BACKEND/api/users/me"
```

Все 8 endpoint'ов должны возвращать `200` или `401/403` (если требуется auth) — но **НЕ 404 / 500**.

---

## 7. Известные ограничения

1. **`accounts.db`** (SQLite в `/app/accounts.db` и `/app/backend/accounts.db`) — локальная sessions БД для миниапки. Размер ~12 КБ. При первом старте инициализируется автоматически.
2. **MiniApp lite vs full**: lite-версия (`/api/miniapp/lite/*`) — быстрая, без heavy JS. Full — `/api/miniapp/core`. Telegram bot должен быть настроен на open lite (через `/api/miniapp/bot/set-menu-lite`).
3. **Mobile native build**: для производственного APK/IPA нужен EAS аккаунт (`eas build`). Web-export через `/api/app/*` доступен прямо сейчас.
4. **Telegram bot setup**: бот должен быть зарегистрирован в @BotFather и `BOT_TOKEN` положен в `backend/.env`.
