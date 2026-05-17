# Fractal & Meta Brain — Deployment & Troubleshooting

История развёртывания, все встреченные ошибки, и их решения. Этот документ
гарантирует, что при последующем разворачивании с GitHub система сразу
приходит в текущее рабочее состояние.

---

## TL;DR — развёртывание с нуля

```bash
# Клонируем репо в /app, кладём .env-ы → выполняем:
bash /app/scripts/bootstrap.sh
```

Скрипт `bootstrap.sh` идемпотентен и под капотом вызывает
`/app/scripts/cold_boot_fractal.sh`, который доразворачивает Fractal/Meta
Brain.  После завершения 9 endpoints должны вернуть HTTP 200.

---

## 1. Архитектурное решение

**Дано:** В `/app/legacy/backend-src/` лежит ~22k строк TypeScript исходников
Fractal v2.1 engine, помеченные в `README_ABANDONED.md` как QUARANTINED
("read, understand, re-implement natively in FastAPI").

**Проблема:** Полная порт-миграция движков (Replay / Synthetic / Hybrid /
BTC × SPX overlay) на Python — 8-15 часов работы.  Логика чрезвычайно
сложная (cosine-similarity по 6 годам, regime-guarded blending).

**Решение:** По прямому распоряжению owner-а — реанимирован Node sidecar
из quarantine и подключён как отдельный supervisor-процесс на порту 8003.
Python FastAPI остаётся canonical runtime и проксирует только fractal-
specific routes через `routes/fractal_sidecar_proxy.py`.

**Что добавлено в `/app/legacy/`:**
- `sidecar-server.ts` — минимальная Fastify-обвязка, поднимает только Fractal plugin
- `package.json`, `tsconfig.json` — копии из `/app/backend/`
- `src/` → symlink на `backend-src/`
- `node_modules/` — устанавливается `yarn install`
- 7 stub-файлов в `modules/fractal/memory/` (audit-логика, не влияет на прогноз)
- `freeze/freeze-manifest.json` — placeholder для гvернанс-системы

---

## 2. Все ошибки и их решения

### 2.1 Прямая линия на графике (баг 1) — линейная интерполяция

**Симптом:** Frontend `/fractal/overview` рисует прямую вместо forecast curve.

**Root cause:** В `/app/backend/routes/legacy_compat.py` endpoint `/api/ui/overview`
строил `predicted_series` линейной интерполяцией:
```python
v = last_v * (1.0 + target_pct * frac)  # straight line
```

**Решение:** Добавил `/api/ui/overview` в `fractal_sidecar_proxy.py` чтобы
запросы шли в Node sidecar, где `overview.service.ts` строит реальную
forecast trajectory из median analog cohort.

**Файл:** `/app/backend/routes/fractal_sidecar_proxy.py`

---

### 2.2 Прямая линия на графике (баг 2) — 91-дневная дыра в данных

**Симптом:** После фикса 2.1 прямая всё ещё есть в участке март–май 2026.

**Root cause:** Node sidecar читает BTC из `fractal_canonical_ohlcv` где
последняя свеча была **15 февраля 2026** (CSV bootstrap из репо). Python
`/api/ui/candles` отдавал свежее (до 17 мая). `lightweight-charts`
соединял две валидные точки 91 день апарт прямой линией.

**Решение:** В cold_boot_fractal.sh step 4 — после CSV bootstrap идёт
gap-fill из Python `/api/ui/candles` для последних 2 лет. После:
```
BTC before: 5692 (до 2026-02-15)
BTC after:  5783 (до 2026-05-17), 0 gaps
```

**Файл:** `/app/scripts/cold_boot_fractal.sh` (step 4)

---

### 2.3 Walk-forward forecast trail (концептуальный фикс)

**Запрос:** Чёрная линия на графике должна показывать "что модель думала
тогда", а НЕ повторять свечи. Визуальное расхождение past predictions
vs реальность.

**Root cause:** `/api/prediction/snapshots` возвращал 0 snapshots (collision:
коллекция `prediction_snapshots` уже занята PolyMarket markets, 223 docs
другой схемы).

**Решение:**
1. Создал отдельную коллекцию `fractal_rolling_snapshots`
2. Написал Python backfill `/app/backend/scripts/backfill_rolling_forecasts.py`:
   - Для каждого дня D в [today-365, today] стрид 3
   - Запускает cosine-similarity engine ТОЛЬКО на данных до D
   - Сохраняет 30-day forward curve + анchor price
3. Создал auto-update loop `/app/backend/scripts/rolling_forecast_loop.py`
4. Зарегистрировал в supervisor как `rolling_forecast_loop` (каждые 6h)
5. Создал endpoint в `/app/backend/routes/rolling_snapshots.py` который
   читает из `fractal_rolling_snapshots`, регистрируется в server.py
   ПЕРЕД legacy_compat catchall

**Файлы:**
- `/app/backend/scripts/backfill_rolling_forecasts.py`
- `/app/backend/scripts/rolling_forecast_loop.py`
- `/app/backend/routes/rolling_snapshots.py`
- `/etc/supervisor/conf.d/supervisord_rolling_forecast.conf`

---

### 2.4 Meta Brain endpoints — 10 заглушек

**Симптом:** Endpoint-ы возвращали `note: 'legacy_compat_stub_empty'`:
- /meta-brain-v2/status, /state, /signals/aligned, /drift, /correlation
- /dataset/stats, /dataset/runs, /performance, /influence
- /v10/meta-brain/snapshots

**Решение:** Создан `/app/backend/routes/meta_brain_real.py` который
считает всё из реальных Mongo коллекций. Подключён в server.py ПЕРЕД
legacy_compat чтобы выигрывал коллизию маршрутов.

**Field-name mismatches исправлены:**
- `signal_log.timestamp` (не `ts`)
- `actor_signal_events.actor_handle` (не `actor`)
- `spx_candles.close` flat (не `ohlcv.c`)
- confidence 0-100 → нормализуется в 0-1

**Файл:** `/app/backend/routes/meta_brain_real.py`

---

### 2.5 `/api/mbrain/verdicts/list` — dead upstream

**Симптом:** "All connection attempts failed" → mobile Expo app падает.

**Root cause:** Endpoint в `/app/backend/routes/mbrain_verdicts.py` ходил
на упразднённый Trading Terminal sidecar `http://localhost:8002/api/verdict/open`
(quarantined ещё в 2026-05-12).

**Решение:** Переписал handler `list_verdicts` — теперь читает напрямую
из 13 нативных `<asset>_fractal_forecasts` коллекций, нормализует через
`normalize_verdict_to_decision` и возвращает inspector cards. Source-
независимо от quarantined sidecar.

**Файл:** `/app/backend/routes/mbrain_verdicts.py`

---

### 2.6 Float-precision отображение

**Симптом:** UI рендерит `RANGE (P10–P90) -1.89000000000001% – 4.10999999999999%`.

**Root cause:** В `/app/frontend/src/pages/DxyFractalPage.jsx` значения
выводились без `.toFixed()`.

**Решение:** Все числовые поля обёрнуты в `Number(x).toFixed(2)`.

**Файл:** `/app/frontend/src/pages/DxyFractalPage.jsx`

---

### 2.7 Node sidecar boot failures — отсутствующие модули

**Симптом 1:** `Cannot find module 'modules/fractal/memory/memory.routes.js'`
**Симптом 2:** `Module "...freeze-manifest.json" is not of type "json"`
**Симптом 3:** `Required: MONGODB_URI` (Zod env validation)

**Root cause:** При quarantine удалили subdirectory `modules/fractal/memory/*`
но импорты в `fractal.module.ts` остались.

**Решение:**
1. Создал 7 no-op TS stubs:
   - `memory.routes.ts`, `attribution/attribution.routes.ts`
   - `snapshot/snapshot-writer.service.ts`, `outcome/outcome-resolver.service.ts`
   - `snapshot/prediction-snapshot.model.ts`, `outcome/prediction-outcome.model.ts`
   - `attribution/attribution-aggregator.service.ts`
2. Создал `/app/legacy/freeze/freeze-manifest.json` с минимальным валидным JSON
3. Прокинул `MONGODB_URI="mongodb://localhost:27017/fomo_mobile"` в supervisor env

**Файлы:** см. step 3 cold_boot_fractal.sh + закоммиченные .ts файлы

---

### 2.8 Mongoose использовал `test` DB вместо `fomo_mobile`

**Симптом:** Endpoint возвращает empty matches, хотя данные есть.

**Root cause:** Mongoose connect URI без указания DB → дефолт `test`.

**Решение:** В supervisor env прописать `MONGODB_URI="...:27017/fomo_mobile"`.

---

### 2.9 BTC data schema mismatch

**Симптом:** Node engine ищет `meta.symbol` + `meta.timeframe`, но при
ручном bulk insert документы попали с flat полями `symbol`/`timeframe`.

**Решение:** Все upserts используют схему:
```json
{
  "meta": { "symbol": "BTC", "timeframe": "1d" },
  "ts":   <datetime>,
  "ohlcv": { "o": ..., "h": ..., "l": ..., "c": ..., "v": ... },
  "provenance": { "chosenSource": "..." },
  "quality": { "qualityScore": 1.0, "sanity_ok": true }
}
```

**Файл:** `cold_boot_fractal.sh` (step 4)

---

### 2.10 Route collision — Python legacy перебивает Node proxy

**Симптом:** `/api/fractal/spx` отдаёт пустой DB-shape вместо real engine.

**Root cause:** В `legacy_compat.py` зарегистрирован `@router.get("/fractal/spx")`
который выигрывал у Node proxy (FastAPI = first-match-wins).

**Решение:**
1. Удалил `/fractal/spx` и `/fractal/dxy` из `fractal_overview` handler
   в legacy_compat
2. Создал отдельный `fractal_sidecar_proxy.py` router
3. Подключил его в `server.py` **ПЕРЕД** legacy_compat и
   fractal_ui_adapter

**Порядок include в server.py:**
```python
include(fractal_sidecar_proxy)       # 1. proxy первым
include(rolling_snapshots)            # 2. real Python snapshots
include(meta_brain_real)              # 3. real Meta Brain
# ...
include(legacy_compat)                # последним (catch-all)
```

---

### 2.11 Paywall блокировал просмотр Fractal pages

**Симптом:** Login через Google и paywall overlay "Unlock the full terminal".

**Решение (как в исходном проекте):**
1. `billing_config.paywall_enabled: false` в Mongo
2. `/app/frontend/src/components/PaywallOverlay.jsx` — добавлен hardcoded
   `return null` перед обычной логикой (для free_trial mode)

---

## 3. Файлы, добавленные в репозиторий

```
/app/legacy/sidecar-server.ts                                        # NEW
/app/legacy/backend-src/modules/fractal/memory/*.ts (7 stubs)        # NEW
/app/legacy/freeze/freeze-manifest.json                              # NEW
/app/backend/routes/fractal_sidecar_proxy.py                         # NEW
/app/backend/routes/rolling_snapshots.py                             # NEW
/app/backend/routes/meta_brain_real.py                               # NEW
/app/backend/scripts/backfill_rolling_forecasts.py                   # NEW
/app/backend/scripts/rolling_forecast_loop.py                        # NEW
/app/backend/server.py                                               # MODIFIED (add 3 includes)
/app/backend/routes/legacy_compat.py                                 # MODIFIED (remove conflicts)
/app/backend/routes/mbrain_verdicts.py                               # MODIFIED (drop upstream dep)
/app/backend/fractal_forecast/native_engine.py                       # MODIFIED (new public fn)
/app/frontend/src/pages/DxyFractalPage.jsx                           # MODIFIED (toFixed)
/app/frontend/src/components/PaywallOverlay.jsx                      # MODIFIED (bypass)
/app/scripts/cold_boot_fractal.sh                                    # NEW
/app/scripts/bootstrap.sh                                            # MODIFIED (call fractal step)
/app/FRACTAL_API.md                                                  # NEW
/app/FRACTAL_DEPLOYMENT.md                                           # NEW (this file)
/etc/supervisor/conf.d/supervisord_node_sidecar.conf                 # NEW (system)
/etc/supervisor/conf.d/supervisord_rolling_forecast.conf             # NEW (system)
```

---

## 4. Troubleshooting

### Node sidecar не стартует

```bash
tail -100 /var/log/supervisor/node_sidecar.out.log
tail -100 /var/log/supervisor/node_sidecar.err.log
```

Типичные причины:
- `Cannot find module '...'` → проверь stub файлы в `modules/fractal/memory/`
- `Required: MONGODB_URI` → проверь supervisor env (должно быть `mongodb://localhost:27017/fomo_mobile`)
- `port 8003 busy` → `pkill -f "tsx sidecar"` и `supervisorctl restart node_sidecar`

### Прямая линия вернулась на графике

```bash
# Проверь что endpoint реально возвращает данные Node sidecar
curl -s "http://127.0.0.1:8001/api/ui/overview?asset=btc&horizon=90" | python3 -c "
import sys, json
d = json.load(sys.stdin)
a = d['charts']['actual']
print(f'actual={len(a)} first={a[0][\"t\"]} last={a[-1][\"t\"]}')
"
```

Если actual ≠ 730 точек на горизонт 2 года — есть gap. Запусти gap-fill:
```bash
bash /app/scripts/cold_boot_fractal.sh
```

### Meta Brain endpoint вернул `legacy_compat_stub_empty`

`meta_brain_real` router не подключился в server.py — проверь логи backend:
```bash
tail -50 /var/log/supervisor/backend.err.log | grep MetaBrainReal
```
Должно быть `[MetaBrainReal] mounted: ...` (если import-ошибка — сообщение покажет detail).

### Rolling snapshots пусто (count=0)

```bash
# Manual backfill
/root/.venv/bin/python3 /app/backend/scripts/backfill_rolling_forecasts.py \
  --days 365 --stride 3 --horizon 30 --window 120 --topk 10 --wipe
```

Затем перезапусти backend:
```bash
supervisorctl restart backend
```

### Mongo connection refused

```bash
supervisorctl status mongodb
supervisorctl restart mongodb
```

---

## 5. Smoke test после деплоя

После любого `bootstrap.sh` или `cold_boot_fractal.sh` 9 endpoints должны
ответить HTTP 200 (smoke test встроен в скрипт):

```
/api/fractal/v2.1/overlay?symbol=BTC&horizon=30&windowLen=120&topK=10&aftermathDays=30
/api/fractal/dxy?focus=30d
/api/fractal/spx?focus=30d
/api/overlay/coeffs?base=BTC&driver=SPX&horizon=30d
/api/ui/overview?asset=btc&horizon=90
/api/prediction/snapshots?asset=BTC&view=hybrid&horizon=90&limit=10
/api/meta-brain-v2/status
/api/meta-brain-v2/correlation?window_days=120
/api/mbrain/verdicts/list?limit=5
```

Если какие-то возвращают не 200 — см. соответствующий раздел Troubleshooting.

---

## 6. Что НЕ перенесено и почему

| Что | Где | Почему отложено |
|---|---|---|
| Memory audit module (TP/FP labelling прошлых predictions) | `modules/fractal/memory/` — 7 stubs | Не влияет на прогноз. Это только retrospective accuracy. Доделать = 2-4 часа. |
| Rolling backfill для SPX/DXY | scripts/ — пока BTC-only | Frontend SPX/DXY страницы используют свои Node endpoint-ы напрямую. Расширение backfill = 30 минут. |
| ML-trained weights для Meta Brain aggregator | trading_runtime | Сейчас static-policy gate (min_active=3, min_conf=0.45). ML-обучение = отдельный проект. |
| Backfill candles из live source автоматически | в cron | Пока полагается на манульный gap-fill при deploy. |

---

## 7. Контракты данных

### `fractal_canonical_ohlcv`
```json
{
  "meta":  { "symbol": "BTC", "timeframe": "1d" },
  "ts":    ISODate,
  "ohlcv": { "o": float, "h": float, "l": float, "c": float, "v": float },
  "provenance": { "chosenSource": str },
  "quality": { "qualityScore": float, "sanity_ok": bool }
}
```

### `fractal_rolling_snapshots`
```json
{
  "asset":       "BTC",
  "view":        "hybrid",
  "horizonDays": 30,
  "asOf":        ISO string,
  "asOfDate":    "2026-05-17",
  "asOfPrice":   float,
  "series":      [{ "t": ISO, "v": float }, ...],
  "metadata":    { "stance": "BULLISH|BEARISH|HOLD", "confidence": float, "analogCount": int, "source": "rolling_v1" },
  "hash":        str
}
```

---

## 8. Что проверить в коммите/PR

- [ ] `/app/legacy/sidecar-server.ts` присутствует
- [ ] 7 stub-файлов в `/app/legacy/backend-src/modules/fractal/memory/` присутствуют
- [ ] `/app/backend/routes/{fractal_sidecar_proxy,rolling_snapshots,meta_brain_real}.py` присутствуют
- [ ] `/app/backend/scripts/{backfill_rolling_forecasts,rolling_forecast_loop}.py` присутствуют
- [ ] `/app/scripts/cold_boot_fractal.sh` помечен исполняемым (`chmod +x`)
- [ ] В `server.py` есть 3 include до legacy_compat
- [ ] CSV-семена `BTCUSD_daily.csv`, `BTC_legacy_2010.csv` остались в `/app/backend/data/fractal/bootstrap/`
- [ ] `package.json` и `tsconfig.json` в `/app/legacy/` (либо script их скопирует)

---

## 9. История изменений

- **2026-05-17** — Initial Fractal & Meta Brain deployment
  - Реанимирован Node sidecar из quarantine
  - Создан rolling forecast pipeline (walk-forward backfill)
  - Заменены 10 Meta Brain заглушек на real-data implementations
  - Подключены 3 supervisor процесса (node_sidecar, rolling_forecast_loop)
  - Документирован deployment flow
