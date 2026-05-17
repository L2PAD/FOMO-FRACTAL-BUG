"""
Telegram Sequence Engine — Multi-step push sequences.

Instead of single messages, delivers a SEQUENCE over time:
  T0:   Signal alert (entry forming)
  T+1h: Entry active now
  T+3h: Window closing
  T+6h: Missed profit / outcome

Also handles REGRET messages for missed signals.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_mobile")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


# ══════════════════════════════════════
# SEQUENCE TEMPLATES
# ══════════════════════════════════════

def build_sequence(asset: str, direction: str, confidence: int, edge_pct: float = 5.0) -> list:
    """
    Build a 4-step Telegram sequence for a signal.
    Returns list of {delay_minutes, message_en, message_ru, step}.
    """
    dir_word = "Buy" if direction.upper() in ("BUY", "BULLISH", "LONG") else "Sell" if direction.upper() in ("SELL", "BEARISH", "SHORT") else "Watch"

    return [
        # T0 — Signal detected
        {
            "step": 0,
            "delay_minutes": 0,
            "message_en": (
                f"🚨 {asset} SIGNAL\n\n"
                f"{dir_word} {asset} — entry forming\n"
                f"Expected move: +{edge_pct:.0f}–{edge_pct + 3:.0f}%\n\n"
                f"Most users will enter late\n\n"
                f"→ Open signal"
            ),
            "message_ru": (
                f"🚨 {asset} СИГНАЛ\n\n"
                f"{dir_word} {asset} — вход формируется\n"
                f"Ожидаемое движение: +{edge_pct:.0f}–{edge_pct + 3:.0f}%\n\n"
                f"Большинство войдут поздно\n\n"
                f"→ Открыть сигнал"
            ),
        },
        # T+1h — Entry active
        {
            "step": 1,
            "delay_minutes": 60,
            "message_en": (
                f"⚡ {asset} — Entry active now\n\n"
                f"Setup confirmed\n"
                f"PRO users already inside\n\n"
                f"→ See entry"
            ),
            "message_ru": (
                f"⚡ {asset} — Вход активен\n\n"
                f"Сетап подтверждён\n"
                f"PRO уже внутри\n\n"
                f"→ Смотреть вход"
            ),
        },
        # T+3h — Window closing
        {
            "step": 2,
            "delay_minutes": 180,
            "message_en": (
                f"⏳ {asset} — Window closing\n\n"
                f"Entry window narrowing\n"
                f"Last chance for optimal entry\n\n"
                f"→ Enter now"
            ),
            "message_ru": (
                f"⏳ {asset} — Окно закрывается\n\n"
                f"Окно входа сужается\n"
                f"Последний шанс для оптимального входа\n\n"
                f"→ Войти сейчас"
            ),
        },
        # T+6h — Outcome / missed
        {
            "step": 3,
            "delay_minutes": 360,
            "message_en": (
                f"📈 {asset} already moved\n\n"
                f"Signal played out\n"
                f"Next setup is forming\n\n"
                f"→ Catch the next one"
            ),
            "message_ru": (
                f"📈 {asset} уже двинулся\n\n"
                f"Сигнал отработал\n"
                f"Следующий сетап формируется\n\n"
                f"→ Не пропусти следующий"
            ),
        },
    ]


def schedule_sequence(asset: str, direction: str, confidence: int, edge_pct: float = 5.0) -> dict:
    """
    Schedule a full Telegram sequence. Stores steps in DB for background runner.
    """
    now = datetime.now(timezone.utc)
    steps = build_sequence(asset, direction, confidence, edge_pct)

    sequence_id = f"seq_{asset}_{int(now.timestamp())}"

    for step in steps:
        fire_at = now + timedelta(minutes=step["delay_minutes"])
        db.telegram_sequences.update_one(
            {"sequenceId": sequence_id, "step": step["step"]},
            {"$set": {
                "sequenceId": sequence_id,
                "asset": asset,
                "step": step["step"],
                "fireAt": fire_at,
                "fired": False,
                "message_en": step["message_en"],
                "message_ru": step["message_ru"],
                "createdAt": now,
            }},
            upsert=True,
        )

    logger.info(f"[Sequence] Scheduled {len(steps)} steps for {asset}: {sequence_id}")
    return {"sequenceId": sequence_id, "steps": len(steps), "asset": asset}


def get_pending_sequence_messages() -> list:
    """
    Get all sequence messages that are due to fire.
    Called by the background runner.
    """
    now = datetime.now(timezone.utc)
    pending = list(db.telegram_sequences.find({
        "fired": False,
        "fireAt": {"$lte": now},
    }).sort("fireAt", 1).limit(20))

    return pending


def mark_sequence_fired(doc_id) -> None:
    """Mark a sequence step as fired."""
    db.telegram_sequences.update_one(
        {"_id": doc_id},
        {"$set": {"fired": True, "firedAt": datetime.now(timezone.utc)}}
    )


# ══════════════════════════════════════
# MISSED PROFIT MESSAGES
# ══════════════════════════════════════

def build_missed_profit_message(asset: str, pnl_pct: float, lang: str = "en") -> str:
    """Build a regret/missed profit message."""
    pnl_str = f"+{pnl_pct:.1f}" if pnl_pct > 0 else f"{pnl_pct:.1f}"

    # Money framing ($3k position)
    money = abs(round(3000 * pnl_pct / 100))

    if lang == "ru":
        return (
            f"⚠️ Ты это видел\n\n"
            f"{asset} двинулся {pnl_str}%\n"
            f"≈ ${money:,} на позиции $3,000\n\n"
            f"Следующий сетап формируется\n\n"
            f"→ Не пропусти снова"
        )

    return (
        f"⚠️ You saw this signal\n\n"
        f"{asset} moved {pnl_str}%\n"
        f"≈ ${money:,} on $3,000 position\n\n"
        f"Next setup is forming\n\n"
        f"→ Don't miss again"
    )


def build_outcome_message(asset: str, pnl_pct: float, lang: str = "en") -> str:
    """Build a positive outcome message."""
    pnl_str = f"+{pnl_pct:.1f}" if pnl_pct > 0 else f"{pnl_pct:.1f}"
    money = abs(round(3000 * pnl_pct / 100))

    if lang == "ru":
        return (
            f"✅ Сигнал закрыт\n\n"
            f"{asset} {pnl_str}%\n"
            f"≈ ${money:,} на позиции $3,000\n\n"
            f"Новый сетап формируется\n\n"
            f"→ Лови следующий"
        )

    return (
        f"✅ Signal closed\n\n"
        f"{asset} {pnl_str}%\n"
        f"≈ ${money:,} on $3,000 position\n\n"
        f"New setup forming\n\n"
        f"→ Catch next one"
    )


def check_missed_profits() -> list:
    """
    Check for recent signals that moved but user didn't act.
    Returns list of missed profit events for feed + Telegram.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    # Find resolved shadow trades with positive PnL
    resolved = list(db.shadow_trades.find({
        "status": "RESOLVED",
        "pnl": {"$gt": 0},
        "resolvedAt": {"$gte": cutoff},
    }).sort("resolvedAt", DESCENDING).limit(5))

    missed = []
    for trade in resolved:
        asset = trade.get("symbol", "BTC")
        pnl = trade.get("pnl", 0)
        missed.append({
            "asset": asset,
            "pnl": round(pnl, 2),
            "message_en": build_missed_profit_message(asset, pnl, "en"),
            "message_ru": build_missed_profit_message(asset, pnl, "ru"),
        })

    return missed
