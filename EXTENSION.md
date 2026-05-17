# FOMO X Connect - Browser Extension

## Что это?

FOMO X Connect - это Chrome расширение, которое позволяет безопасно синхронизировать вашу Twitter/X сессию с FOMO платформой.

## Как это работает?

### "Непрямой метод" (Indirect Method)

**Ключевая особенность**: Backend НИКОГДА не делает прямые запросы к Twitter. Все запросы к Twitter API происходят **из вашего браузера**:

```
┌──────────────────────┐         ┌─────────────────┐
│  Browser Extension   │ ──(1)── │   Twitter API   │
│  (ваш браузер)       │ ◄──(2)── │   (x.com)       │
└──────────────────────┘         └─────────────────┘
          │
          │ (3) Отправка данных
          ▼
┌──────────────────────┐
│     FOMO Backend     │
│  (только хранение)   │
└──────────────────────┘
```

1. Расширение делает запрос к Twitter из вашего браузера
2. Twitter видит ваш реальный IP, cookies и fingerprint
3. Полученные данные отправляются на backend для хранения

### Почему это важно?

- **Twitter не блокирует**: Запросы идут от реального пользователя, не от сервера
- **Безопасность**: Ваши cookies не передаются на сервер (только session sync)
- **Надёжность**: Нет rate limits от Twitter для backend

## Установка

### Вариант 1: Загрузка как unpacked extension

1. Откройте Chrome и перейдите в `chrome://extensions/`
2. Включите "Режим разработчика" (Developer mode)
3. Нажмите "Загрузить распакованное расширение" (Load unpacked)
4. Выберите папку `fomo_extension_v1.3.0`

### Вариант 2: Chrome Web Store (когда будет опубликовано)

Скоро будет доступно...

## Использование

1. Откройте Twitter (x.com) и войдите в свой аккаунт
2. Кликните на иконку расширения FOMO X Connect
3. Введите URL вашей платформы и API ключ
4. Нажмите "Sync Session"

## Разработчикам

### Структура файлов

```
fomo_extension_v1.3.0/
├── manifest.json           # Конфигурация расширения (MV3)
├── background.js           # Service Worker
├── popup.html             # UI расширения
├── popup.js               # Логика UI
├── twitter-fetcher.js     # Запросы к Twitter API
├── cookie-quality-checker.js # Проверка cookies
├── backend-error-mapper.js   # Обработка ошибок
└── icons/                 # Иконки
```

### Ключевые endpoints backend

- `POST /api/v4/twitter/preflight-check/extension` - Проверка перед синхронизацией
- `POST /api/v4/twitter/sessions/webhook` - Синхронизация cookies
- `GET /api/v4/twitter/accounts` - Список аккаунтов
- `POST /api/v4/twitter/ingest` - Приём данных от extension

### Безопасность

- Cookies передаются только для session sync
- API ключ хранится в chrome.storage.local
- Все запросы используют HTTPS
