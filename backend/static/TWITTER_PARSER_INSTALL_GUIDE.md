# Twitter Parser V2 - Инструкция по установке

## 📦 Скачивание пакета

**Из админки:**
1. Зайдите в админку: https://expo-telegram-web.preview.emergentagent.com/admin
2. Перейдите в раздел **Twitter** → **Parser**
3. Нажмите кнопку **"Скачать парсер"** или используйте прямую ссылку:
   ```
   GET /api/admin/twitter-parser/download-parser
   ```

**Напрямую (с авторизацией):**
```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  https://expo-telegram-web.preview.emergentagent.com/api/admin/twitter-parser/download-parser \
  -o twitter-parser-v2.zip
```

---

## 🚀 Установка и настройка

### 1. Распакуйте архив

```bash
unzip twitter-parser-v2.zip
cd twitter-parser-v2
```

### 2. Установите зависимости

```bash
# Установка Node.js зависимостей
yarn install

# Установка Playwright (браузер Chromium)
npx playwright install chromium
```

### 3. Настройка окружения

Создайте файл `.env` (или скопируйте `.env.example`):

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017/intelligence_engine

# Server
PORT=8004

# Twitter Parser V2
PARSER_VERSION=2.0
PARSER_MODE=production

# Session storage
SESSION_DIR=./sessions
COOKIE_DIR=./cookies

# Proxy (опционально)
PROXY_ENABLED=false
```

---

## 🔐 Экспорт cookies (ВАЖНО!)

Для работы парсера необходимы актуальные cookies из Twitter аккаунта.

### Шаг 1: Запустите экспорт

```bash
yarn export-cookies
```

### Шаг 2: Следуйте инструкциям

Скрипт откроет браузер и попросит:
1. **Введите ID сессии** (например: `main_account`, `account1`)
2. **Введите username** Twitter аккаунта (например: `@crypto_trader`)
3. **Введите proxy URL** (опционально, нажмите Enter если нет)
4. **Залогинтесь** в открывшемся браузере Twitter
5. **Нажмите Enter** после успешного логина

Cookies сохранятся в `./cookies/<session_id>.json`

### Шаг 3: Проверьте сессию

```bash
yarn test-session main_account
```

Если всё ОК, вы увидите:
```
✓ Session valid
✓ Cookies loaded: 15
✓ Twitter auth: OK
✓ Profile: @crypto_trader
```

---

## 🎯 Запуск парсера

### Development mode (с hot-reload)

```bash
yarn dev
```

### Production mode

```bash
yarn start
```

Сервер запустится на порту **8004** (или PORT из .env)

---

## 📡 API Endpoints

### Health Check
```bash
GET /health
```

**Response:**
```json
{
  "ok": true,
  "version": "2.0",
  "sessions": 1
}
```

### Управление сессиями

**Список сессий:**
```bash
GET /sessions
```

**Добавить сессию:**
```bash
POST /sessions
Content-Type: application/json

{
  "sessionId": "account2",
  "username": "@trader2",
  "proxy": "http://user:pass@proxy.com:8080"
}
```

**Проверить сессию:**
```bash
POST /sessions/:id/test
```

**Удалить сессию:**
```bash
DELETE /sessions/:id
```

### Парсинг данных

**Поиск твитов:**
```bash
POST /search/:keyword
Content-Type: application/json

{
  "sessionId": "main_account",
  "maxResults": 50
}
```

**Твиты пользователя:**
```bash
POST /tweets/:username
Content-Type: application/json

{
  "sessionId": "main_account",
  "limit": 20
}
```

**Профиль пользователя:**
```bash
GET /profile/:username?sessionId=main_account
```

---

## 🛡️ Архитектура безопасности

### 1. Cookie-based авторизация
- ✅ Без логина каждый раз
- ✅ Cookies хранятся локально в `./cookies/`
- ✅ Сессии persistent (не теряются при перезапуске)

### 2. Anti-detection
- ✅ Playwright (лучше маскируется чем Puppeteer)
- ✅ WebGL fingerprint randomization
- ✅ Canvas noise injection
- ✅ User-Agent rotation
- ✅ Viewport randomization

### 3. Proxy support
- ✅ HTTP/HTTPS proxies
- ✅ SOCKS5 proxies
- ✅ Резидентные прокси (рекомендуется)
- ✅ Rotation по сессиям

### 4. Rate limiting
- ✅ Интеллектуальные задержки
- ✅ Scroll throttling
- ✅ Request batching

---

## 🔧 Интеграция с основной системой

### Подключение к FOMO Intelligence

1. **Запустите parser как microservice:**
   ```bash
   cd twitter-parser-v2
   yarn start
   ```

2. **Настройте environment в основном backend:**
   ```bash
   # /app/backend/.env
   TWITTER_PARSER_URL=http://localhost:8004
   TWITTER_PARSER_ENABLED=true
   ```

3. **Перезапустите основной backend:**
   ```bash
   supervisorctl restart backend
   ```

4. **Проверьте интеграцию:**
   ```bash
   curl http://localhost:8001/api/twitter/health
   ```

---

## 📊 Мониторинг

### Логи парсера

```bash
# Real-time логи
yarn logs

# или напрямую
tail -f logs/parser.log
```

### Метрики

**Статус сессий:**
```bash
curl http://localhost:8004/sessions
```

**Health check:**
```bash
curl http://localhost:8004/health
```

---

## 🐛 Troubleshooting

### Проблема: "Could not log you in"

**Решение:**
1. Убедитесь что cookies актуальны
2. Перезапустите `yarn export-cookies`
3. Проверьте не заблокирован ли аккаунт

### Проблема: "Browser crash"

**Решение:**
1. Увеличьте memory limit:
   ```bash
   export NODE_OPTIONS="--max_old_space_size=4096"
   ```
2. Перезапустите парсер

### Проблема: "Proxy timeout"

**Решение:**
1. Проверьте proxy URL
2. Попробуйте без proxy
3. Смените proxy provider

### Проблема: "Rate limited"

**Решение:**
1. Уменьшите частоту запросов
2. Добавьте больше сессий
3. Используйте резидентные прокси

---

## 📁 Структура проекта

```
twitter-parser-v2/
├── src/
│   ├── browser/          # Playwright browser management
│   │   ├── browser-manager.ts
│   │   ├── session-manager.ts
│   │   └── twitter-client.ts
│   ├── scroll/           # Intelligent scrolling
│   │   ├── scroll.engine.ts
│   │   ├── scroll.policies.ts
│   │   └── risk.assessor.ts
│   ├── queue/            # Task queue (MongoDB)
│   │   ├── mongo-task-queue.ts
│   │   ├── mongo-task-worker.ts
│   │   └── twitter.runtime.ts
│   ├── tools/            # CLI утилиты
│   │   ├── export-cookies.ts
│   │   ├── test-session.ts
│   │   └── auto-refresh.ts
│   ├── server.ts         # Main API server
│   └── config.ts         # Configuration
├── extension/            # Browser extension (опционально)
│   ├── background.js
│   ├── manifest.json
│   └── popup.html
├── package.json
├── tsconfig.json
└── README.md
```

---

## 🎓 Дополнительные команды

**Экспорт cookies:**
```bash
yarn export-cookies
```

**Тест сессии:**
```bash
yarn test-session <session_id>
```

**Auto-refresh cookies:**
```bash
yarn auto-refresh
```

**Очистка старых cookies:**
```bash
yarn clean-cookies
```

**Проверка всех сессий:**
```bash
yarn validate-all
```

---

## ⚙️ Конфигурация (расширенная)

Полный `.env` пример:

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017/intelligence_engine

# Server
PORT=8004
HOST=0.0.0.0

# Parser
PARSER_VERSION=2.0
PARSER_MODE=production
MAX_CONCURRENT_SESSIONS=5
SESSION_TIMEOUT=300000

# Storage
SESSION_DIR=./sessions
COOKIE_DIR=./cookies
LOG_DIR=./logs

# Proxy
PROXY_ENABLED=false
PROXY_ROTATION=true
PROXY_POOL_SIZE=10

# Rate Limiting
SCROLL_DELAY_MIN=2000
SCROLL_DELAY_MAX=5000
REQUEST_DELAY=1000
BATCH_SIZE=50

# Anti-detection
RANDOMIZE_VIEWPORT=true
RANDOMIZE_USER_AGENT=true
INJECT_CANVAS_NOISE=true
INJECT_WEBGL_NOISE=true

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
LOG_LEVEL=info
```

---

## 📞 Поддержка

**Проблемы с установкой?**
- Проверьте логи: `tail -f logs/parser.log`
- Проверьте версию Node.js: `node -v` (требуется >= 18.0)
- Проверьте версию Playwright: `npx playwright --version`

**Вопросы по интеграции?**
- Документация API: http://localhost:8004/docs (если включен Swagger)
- Проверьте connectivity: `curl http://localhost:8004/health`

---

## ✨ Changelog

**v2.0** (текущая версия)
- ✅ Playwright вместо Puppeteer
- ✅ Cookie-based sessions
- ✅ MongoDB task queue
- ✅ Intelligent scrolling
- ✅ Risk assessment
- ✅ Proxy rotation
- ✅ Anti-detection scripts

---

**Готово к использованию!** 🚀

Следуйте инструкциям выше для успешной установки и интеграции Twitter Parser V2 с вашей системой FOMO Intelligence.
