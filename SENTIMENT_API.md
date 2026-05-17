# Sentiment SDK — Интеграция

## Быстрый старт

### Python
```python
from sentiment_sdk import Sentiment

client = Sentiment(
    url='<YOUR_SERVER_URL>',
    key='<YOUR_API_KEY>',
)

result = client.analyze("Bitcoin ETF approved!", source="twitter")
print(result["label"])       # POSITIVE
print(result["score"])       # 0.72
```

### TypeScript
```typescript
import { Sentiment } from './sentiment-sdk'

const client = new Sentiment({
    url: '<YOUR_SERVER_URL>',
    key: '<YOUR_API_KEY>',
})

const result = await client.analyze('Bitcoin ETF approved!', 'twitter')
console.log(result.label)       // POSITIVE
console.log(result.score)       // 0.72
```

---

## Методы

| Метод | Описание |
|-------|----------|
| `analyze(text, source?)` | Анализ одного текста |
| `batch(items, source?)` | Пакетный анализ (до 100) |
| `normalize(text)` | Очистка + токены + язык |
| `health()` | Статус движка |

source: `twitter`, `news`, `telegram`, `article`, `headline`, `user`

---

## Формат ответа — analyze

```json
{
  "label": "POSITIVE",
  "score": 0.62,
  "source": "twitter",
  "meta": {
    "confidence": "HIGH",
    "confidenceScore": 0.71,
    "processingTimeMs": 0.3,
    "cached": false
  }
}
```

- `label` — POSITIVE / NEUTRAL / NEGATIVE
- `score` — 0.0 ... 1.0
- `confidence` — LOW / MEDIUM / HIGH

---

## Пакетный анализ

```python
result = client.batch([
    {"id": "1", "text": "BTC breakout"},
    {"id": "2", "text": "Market crash"},
], source="news")
```

---

## Ошибки

| Код | Причина |
|-----|---------|
| 401 | Нет ключа |
| 403 | Неверный ключ |
| 400 | Пустой text |
| 429 | Лимит 1000 req/min |
