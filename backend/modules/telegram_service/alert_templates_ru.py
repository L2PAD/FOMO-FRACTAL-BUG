"""
Alert Templates (Russian)
=========================

Все шаблоны сообщений на русском языке для Telegram.
Используется alert_code → RU template mapping.

Структура сообщения:
- ICON (🔴🟠🟡🟢🔵)
- TITLE
- DESCRIPTION
- IMPACT
- ACTION
"""

from typing import Dict, Any
from datetime import datetime


class AlertSeverity:
    CRITICAL = "CRITICAL"  # 🔴
    HIGH = "HIGH"          # 🔴
    MEDIUM = "MEDIUM"      # 🟠
    WARNING = "WARNING"    # 🟡
    INFO = "INFO"          # 🔵
    RECOVERY = "RECOVERY"  # 🟢


SEVERITY_ICONS = {
    AlertSeverity.CRITICAL: "🔴",
    AlertSeverity.HIGH: "🔴",
    AlertSeverity.MEDIUM: "🟠",
    AlertSeverity.WARNING: "🟡",
    AlertSeverity.INFO: "🔵",
    AlertSeverity.RECOVERY: "🟢"
}


# =============================================================================
# ALERT TEMPLATES
# =============================================================================

ALERT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    
    # =========================================================================
    # 1. ИСТОЧНИКИ ДАННЫХ (Data Sources)
    # =========================================================================
    
    "source_down": {
        "severity": AlertSeverity.CRITICAL,
        "category": "sources",
        "cooldown_minutes": 30,
        "template": """🔴 ПРОБЛЕМА С ИСТОЧНИКОМ ДАННЫХ

Источник: {source}

Источник перестал отвечать.

Что это значит:
данные из этого источника временно не обновляются.

Рекомендуется:
проверить источник в админке."""
    },
    
    "source_degraded": {
        "severity": AlertSeverity.MEDIUM,
        "category": "sources",
        "cooldown_minutes": 30,
        "template": """🟠 УХУДШЕНИЕ РАБОТЫ ИСТОЧНИКА

Источник: {source}

Источник отвечает нестабильно.

Процент ошибок: {error_rate}%

Это может повлиять на обновление данных."""
    },
    
    "source_recovered": {
        "severity": AlertSeverity.RECOVERY,
        "category": "sources",
        "cooldown_minutes": 5,
        "template": """🟢 ИСТОЧНИК ВОССТАНОВЛЕН

Источник: {source}

Источник снова работает стабильно.

Время простоя: {downtime}"""
    },
    
    "source_slow": {
        "severity": AlertSeverity.WARNING,
        "category": "sources",
        "cooldown_minutes": 60,
        "template": """🟡 МЕДЛЕННЫЙ ОТВЕТ ИСТОЧНИКА

Источник: {source}

Среднее время ответа выросло до {latency} сек.

Это может замедлить обновление данных."""
    },
    
    "source_missing_api_key": {
        "severity": AlertSeverity.CRITICAL,
        "category": "sources",
        "cooldown_minutes": 120,
        "template": """🔴 ОТСУТСТВУЕТ API КЛЮЧ

Источник: {source}

Для работы источника требуется API ключ.

Рекомендуется:
добавить ключ в разделе Providers."""
    },
    
    # =========================================================================
    # 2. ПАРСЕРЫ (Parser Monitoring)
    # =========================================================================
    
    "parser_failed": {
        "severity": AlertSeverity.HIGH,
        "category": "parsers",
        "cooldown_minutes": 15,
        "template": """🔴 ОШИБКА ПАРСЕРА

Парсер: {parser}

Парсер не смог получить данные.

Попыток подряд: {attempts}

Система продолжит попытки автоматически."""
    },
    
    "parser_stopped": {
        "severity": AlertSeverity.CRITICAL,
        "category": "parsers",
        "cooldown_minutes": 30,
        "template": """🔴 ПАРСЕР ОСТАНОВИЛСЯ

Парсер: {parser}

Парсер не выполнялся более {time}.

Рекомендуется проверить конфигурацию."""
    },
    
    "parser_recovered": {
        "severity": AlertSeverity.RECOVERY,
        "category": "parsers",
        "cooldown_minutes": 5,
        "template": """🟢 ПАРСЕР СНОВА РАБОТАЕТ

Парсер: {parser}

Работа восстановлена."""
    },
    
    "parser_data_empty": {
        "severity": AlertSeverity.WARNING,
        "category": "parsers",
        "cooldown_minutes": 60,
        "template": """🟡 ПАРСЕР ВЕРНУЛ ПУСТЫЕ ДАННЫЕ

Парсер: {parser}

Источник не вернул новых данных.

Это может быть нормально, если данные не обновлялись."""
    },
    
    # =========================================================================
    # 3. ОЧЕРЕДИ ЗАДАЧ (Queues)
    # =========================================================================
    
    "queue_overflow": {
        "severity": AlertSeverity.CRITICAL,
        "category": "queues",
        "cooldown_minutes": 15,
        "template": """🔴 ОЧЕРЕДЬ ЗАДАЧ ПЕРЕПОЛНЕНА

Количество задач: {jobs}

Система не успевает обрабатывать данные.

Возможная причина:
перегрузка парсеров или медленная работа источников."""
    },
    
    "queue_slow_processing": {
        "severity": AlertSeverity.MEDIUM,
        "category": "queues",
        "cooldown_minutes": 30,
        "template": """🟠 МЕДЛЕННАЯ ОБРАБОТКА ДАННЫХ

Среднее время обработки: {time}

Это может привести к задержкам в обновлении данных."""
    },
    
    "queue_recovered": {
        "severity": AlertSeverity.RECOVERY,
        "category": "queues",
        "cooldown_minutes": 5,
        "template": """🟢 ОЧЕРЕДЬ НОРМАЛИЗОВАЛАСЬ

Очередь задач снова в норме.

Количество задач: {jobs}"""
    },
    
    # =========================================================================
    # 4. ГРАФ (Knowledge Graph)
    # =========================================================================
    
    "graph_explosion": {
        "severity": AlertSeverity.CRITICAL,
        "category": "graph",
        "cooldown_minutes": 60,
        "template": """🔴 АНОМАЛИЯ В ГРАФЕ

Количество связей резко выросло.

Новых edges: {count}

Рекомендуется проверить данные на дубликаты."""
    },
    
    "graph_growth_anomaly": {
        "severity": AlertSeverity.MEDIUM,
        "category": "graph",
        "cooldown_minutes": 60,
        "template": """🟠 АНОМАЛЬНЫЙ РОСТ ГРАФА

Рост узлов превышает норму.

Новых nodes: {count}

Рекомендуется проверить источники данных."""
    },
    
    "graph_rebuild_failed": {
        "severity": AlertSeverity.CRITICAL,
        "category": "graph",
        "cooldown_minutes": 30,
        "template": """🔴 ОШИБКА ПЕРЕСТРОЕНИЯ ГРАФА

Graph builder завершился с ошибкой.

Ошибка: {error}

Рекомендуется проверить логи."""
    },
    
    # =========================================================================
    # 5. ИНТЕЛЛЕКТУАЛЬНЫЙ СЛОЙ (Narratives)
    # =========================================================================
    
    "narrative_detected": {
        "severity": AlertSeverity.INFO,
        "category": "narratives",
        "cooldown_minutes": 60,
        "template": """🔵 ОБНАРУЖЕН НОВЫЙ НАРРАТИВ

Нарратив: {narrative}

Уровень: emerging

Система начала отслеживать новый тренд."""
    },
    
    "narrative_growth": {
        "severity": AlertSeverity.MEDIUM,
        "category": "narratives",
        "cooldown_minutes": 120,
        "template": """🟠 НАРРАТИВ НАБИРАЕТ СИЛУ

Нарратив: {narrative}

Momentum: {score}

Интерес к теме растёт."""
    },
    
    "narrative_decline": {
        "severity": AlertSeverity.WARNING,
        "category": "narratives",
        "cooldown_minutes": 240,
        "template": """🟡 НАРРАТИВ ТЕРЯЕТ АКТУАЛЬНОСТЬ

Нарратив: {narrative}

Интерес к теме снижается."""
    },
    
    # =========================================================================
    # 6. MOMENTUM ENGINE
    # =========================================================================
    
    "entity_momentum_spike": {
        "severity": AlertSeverity.INFO,
        "category": "momentum",
        "cooldown_minutes": 60,
        "template": """🔵 РЕЗКИЙ РОСТ ИНТЕРЕСА

Сущность: {entity}
Тип: {entity_type}

Momentum: {score}
Velocity: +{velocity}

Структурное влияние сущности быстро растёт."""
    },
    
    "entity_new_discovery": {
        "severity": AlertSeverity.RECOVERY,
        "category": "momentum",
        "cooldown_minutes": 30,
        "template": """🟢 ОБНАРУЖЕНА НОВАЯ СУЩНОСТЬ

Система обнаружила новый проект.

Название: {entity}
Тип: {entity_type}

Система начала сбор данных."""
    },
    
    # =========================================================================
    # 7. СИСТЕМА ДАННЫХ
    # =========================================================================
    
    "data_lag_detected": {
        "severity": AlertSeverity.MEDIUM,
        "category": "data",
        "cooldown_minutes": 30,
        "template": """🟠 ЗАДЕРЖКА ДАННЫХ

Последнее обновление: {time}

Данные могут быть устаревшими."""
    },
    
    "missing_data": {
        "severity": AlertSeverity.WARNING,
        "category": "data",
        "cooldown_minutes": 60,
        "template": """🟡 ОТСУТСТВУЮТ ДАННЫЕ

Тип данных: {dataset}

Часть данных не была загружена."""
    },
    
    # =========================================================================
    # 8. SCHEDULER
    # =========================================================================
    
    "scheduler_job_failed": {
        "severity": AlertSeverity.HIGH,
        "category": "scheduler",
        "cooldown_minutes": 15,
        "template": """🔴 СБОЙ ЗАДАЧИ

Задача: {job}

Задача завершилась ошибкой.

Ошибка: {error}"""
    },
    
    "scheduler_job_slow": {
        "severity": AlertSeverity.MEDIUM,
        "category": "scheduler",
        "cooldown_minutes": 30,
        "template": """🟠 МЕДЛЕННОЕ ВЫПОЛНЕНИЕ ЗАДАЧИ

Задача: {job}

Время выполнения: {time}

Это дольше обычного."""
    },
    
    # =========================================================================
    # 9. ИНФРАСТРУКТУРА
    # =========================================================================
    
    "cpu_overload": {
        "severity": AlertSeverity.CRITICAL,
        "category": "infrastructure",
        "cooldown_minutes": 10,
        "template": """🔴 ВЫСОКАЯ НАГРУЗКА CPU

Нагрузка: {cpu}%

Система может работать медленнее."""
    },
    
    "memory_overflow": {
        "severity": AlertSeverity.CRITICAL,
        "category": "infrastructure",
        "cooldown_minutes": 10,
        "template": """🔴 НЕ ХВАТАЕТ ПАМЯТИ

Использовано: {memory}%

Рекомендуется проверить процессы."""
    },
    
    "disk_space_low": {
        "severity": AlertSeverity.MEDIUM,
        "category": "infrastructure",
        "cooldown_minutes": 60,
        "template": """🟠 МАЛО МЕСТА НА ДИСКЕ

Свободно: {space}

Рекомендуется очистить старые данные."""
    },
    
    # =========================================================================
    # 10. БЕЗОПАСНОСТЬ
    # =========================================================================
    
    "suspicious_activity": {
        "severity": AlertSeverity.CRITICAL,
        "category": "security",
        "cooldown_minutes": 5,
        "template": """🔴 ПОДОЗРИТЕЛЬНАЯ АКТИВНОСТЬ

Обнаружена аномалия в системе.

Описание: {description}

Рекомендуется немедленная проверка."""
    },
    
    # =========================================================================
    # 11. ИНФОРМАЦИОННЫЕ СОБЫТИЯ
    # =========================================================================
    
    "new_source_detected": {
        "severity": AlertSeverity.INFO,
        "category": "info",
        "cooldown_minutes": 120,
        "template": """🔵 ОБНАРУЖЕН НОВЫЙ ИСТОЧНИК

Источник: {source}

Тип данных: {data_type}

Система предлагает добавить его в парсинг."""
    },
    
    "system_restart": {
        "severity": AlertSeverity.INFO,
        "category": "info",
        "cooldown_minutes": 5,
        "template": """🔵 СИСТЕМА ПЕРЕЗАПУЩЕНА

Платформа была перезапущена.

Время запуска: {time}

Все сервисы активны."""
    },
    
    # =========================================================================
    # 12. ЕЖЕДНЕВНЫЙ ОТЧЁТ
    # =========================================================================
    
    "daily_system_report": {
        "severity": AlertSeverity.INFO,
        "category": "reports",
        "cooldown_minutes": 1440,  # 24 hours
        "template": """📊 СОСТОЯНИЕ ПЛАТФОРМЫ

Источники данных
работают: {sources_healthy}
нестабильны: {sources_degraded}
не отвечают: {sources_down}

Парсеры
успешно: {parsers_success}
ошибки: {parsers_errors}

Граф
узлов: {graph_nodes}
связей: {graph_edges}

Momentum
отслеживается: {momentum_tracked}
high momentum: {momentum_high}

Новые сущности: {new_entities}

{status_message}"""
    }
}


def render_alert(alert_code: str, data: Dict[str, Any]) -> str:
    """
    Render alert template with data.
    Returns formatted Russian message.
    """
    template_info = ALERT_TEMPLATES.get(alert_code)
    
    if not template_info:
        return f"⚠️ Неизвестное событие: {alert_code}"
    
    template = template_info["template"]
    
    try:
        message = template.format(**data)
    except KeyError as e:
        message = f"⚠️ Ошибка шаблона {alert_code}: отсутствует {e}"
    
    return message


def get_alert_severity(alert_code: str) -> str:
    """Get severity for alert code"""
    template_info = ALERT_TEMPLATES.get(alert_code)
    return template_info.get("severity", AlertSeverity.INFO) if template_info else AlertSeverity.INFO


def get_alert_cooldown(alert_code: str) -> int:
    """Get cooldown minutes for alert code"""
    template_info = ALERT_TEMPLATES.get(alert_code)
    return template_info.get("cooldown_minutes", 30) if template_info else 30


def get_alert_category(alert_code: str) -> str:
    """Get category for alert code"""
    template_info = ALERT_TEMPLATES.get(alert_code)
    return template_info.get("category", "unknown") if template_info else "unknown"


def get_all_alert_codes() -> list:
    """Get list of all alert codes"""
    return list(ALERT_TEMPLATES.keys())
