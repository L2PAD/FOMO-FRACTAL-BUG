"""
Sentiment SDK
=============
Установка: положить файл в проект.

    from sentiment_sdk import Sentiment

    client = Sentiment(
        url='<YOUR_SERVER_URL>',
        key='<YOUR_API_KEY>',
    )

    result = client.analyze("Bitcoin is pumping!", source="twitter")
    print(result["label"])  # POSITIVE
"""

import requests
from typing import Optional


class Sentiment:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key

    def _request(self, method: str, path: str, body: dict = None):
        resp = requests.request(
            method,
            f"{self.url}/api/v1/sentiment{path}",
            json=body,
            headers={"Content-Type": "application/json", "X-API-Key": self.key},
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok"):
            raise Exception(data.get("message") or data.get("error") or "API error")
        return data["data"]

    def analyze(self, text: str, source: Optional[str] = None) -> dict:
        """Анализ текста. Возвращает label, score, confidence."""
        return self._request("POST", "/analyze", {"text": text, "source": source})

    def batch(self, items: list, source: Optional[str] = None) -> dict:
        """Пакетный анализ (до 100 текстов)."""
        return self._request("POST", "/batch", {"items": items, "source": source})

    def normalize(self, text: str) -> dict:
        """Очистка текста + токены + определение языка."""
        return self._request("POST", "/normalize", {"text": text})

    def health(self) -> dict:
        """Проверка статуса движка."""
        return self._request("GET", "/health")
