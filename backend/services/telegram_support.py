"""
FOMO Telegram Bot Service
Full bot logic: main menu, signals, support, account linking, subscription sync.
Bot: @FOMO_Trading_bot
"""
import os
import logging
import json
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MONGO_URL = os.getenv("MONGO_URL", "")

# ─── MongoDB ───
_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[os.getenv("DB_NAME", "test_database")]
users_col = _db["users"]
support_tickets_col = _db["support_tickets"]
exchange_observations_col = _db["exchange_observations"]

# ─── State tracking ───
_support_mode: dict[int, bool] = {}

# ─── Plan hierarchy for sync ───
PLAN_RANK = {"FREE": 0, "TRIAL": 1, "PRO": 2, "INSTITUTIONAL": 3}

MINIAPP_URL = "https://t.me/FOMO_Trading_bot/app"


def _main_menu_keyboard():
    """Inline keyboard for the main menu."""
    return {
        "inline_keyboard": [
            [
                {"text": "📊 Сигналы", "callback_data": "signals"},
                {"text": "⚙️ Настройка", "callback_data": "setup_signals"},
            ],
            [
                {"text": "⭐ PRO", "callback_data": "pro_status"},
                {"text": "🛟 Поддержка", "callback_data": "support"},
            ],
            [
                {"text": "👤 Аккаунт", "callback_data": "my_account"},
                {"text": "🔗 Привязать", "callback_data": "link_account"},
            ],
        ]
    }


def _back_button():
    """Inline keyboard with just a back-to-menu button."""
    return {
        "inline_keyboard": [
            [{"text": "◀️ Меню", "callback_data": "back_menu"}],
        ]
    }


async def _get_user_by_chat(chat_id: int):
    """Find user by telegramChatId."""
    return await users_col.find_one({"telegramChatId": chat_id})


async def _sync_subscription(user_doc: dict, chat_id: int) -> str:
    """
    Sync subscription between platforms.
    If there's a linked user with a higher plan, upgrade.
    Returns the best plan found.
    """
    current_plan = user_doc.get("plan", "FREE")
    current_rank = PLAN_RANK.get(current_plan, 0)

    # Check if there's another user record with this chat_id that has a better plan
    all_with_chat = users_col.find({"telegramChatId": chat_id})
    best_plan = current_plan
    best_rank = current_rank

    async for u in all_with_chat:
        p = u.get("plan", "FREE")
        r = PLAN_RANK.get(p, 0)
        if r > best_rank:
            best_plan = p
            best_rank = r

    if best_rank > current_rank:
        await users_col.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"plan": best_plan, "updatedAt": datetime.utcnow()}}
        )
        logger.info(f"Subscription synced for {user_doc.get('email')}: {current_plan} -> {best_plan}")
        return best_plan

    return current_plan


async def _get_latest_signal(asset: str = "BTC") -> dict:
    """Get latest signal data for an asset from exchange_observations."""
    obs = await exchange_observations_col.find_one(
        {"symbol": asset.upper()},
        sort=[("timestamp", -1)]
    )
    if not obs:
        return {
            "asset": asset.upper(),
            "decision": "WAIT",
            "confidence": 0.5,
            "price": 0,
            "change24h": 0,
        }

    price = obs.get("price", 0)
    change24h = obs.get("change24h", 0)
    sentiment_up = obs.get("sentimentUp", 50)

    # Simple signal computation (mirrors mobile.py logic)
    score = 0.5
    if change24h > 0:
        score += min(change24h * 2, 0.15)
    else:
        score += max(change24h * 2, -0.15)

    if sentiment_up > 60:
        score += 0.1
    elif sentiment_up < 40:
        score -= 0.1

    change7d = obs.get("change7d", 0)
    if change7d > 0:
        score += min(change7d * 0.5, 0.1)
    else:
        score += max(change7d * 0.5, -0.1)

    score = max(0.15, min(0.95, score))

    if score >= 0.55:
        decision = "BUY"
    elif score <= 0.45:
        decision = "SELL"
    else:
        decision = "WAIT"

    return {
        "asset": asset.upper(),
        "decision": decision,
        "confidence": round(score, 2),
        "price": round(price, 2),
        "change24h": round(change24h, 2),
    }


# ═══════════════════════════════════════════════════
#  HANDLE UPDATES
# ═══════════════════════════════════════════════════

async def handle_update(update: dict) -> list[dict]:
    """
    Process incoming Telegram update.
    Returns a list of response actions [{method, ...}].
    """
    responses = []

    # ─── Callback queries (button presses) ───
    callback = update.get("callback_query")
    if callback:
        chat_id = callback["message"]["chat"]["id"]
        data = callback.get("data", "")
        user_tg = callback.get("from", {})

        # Answer callback to remove loading spinner
        responses.append({
            "method": "answerCallbackQuery",
            "callback_query_id": callback["id"],
        })

        # ── Back to menu ──
        if data == "back_menu":
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": "📋 *Меню FOMO*\n\nВыберите действие:",
                "parse_mode": "Markdown",
                "reply_markup": _main_menu_keyboard(),
            })

        # ── Signals ──
        elif data == "signals":
            linked_user = await _get_user_by_chat(chat_id)
            default_asset = "BTC"
            plan = "FREE"
            if linked_user:
                default_asset = linked_user.get("preferences", {}).get("defaultAsset", "BTC")
                plan = await _sync_subscription(linked_user, chat_id)

            signal = await _get_latest_signal(default_asset)
            decision = signal["decision"]
            confidence = signal["confidence"]
            price = signal["price"]
            change = signal["change24h"]

            # Decision emoji
            if decision == "BUY":
                dec_emoji = "🟢"
            elif decision == "SELL":
                dec_emoji = "🔴"
            else:
                dec_emoji = "🟡"

            # Confidence bar
            conf_pct = int(confidence * 100)
            filled = conf_pct // 10
            bar = "█" * filled + "░" * (10 - filled)

            change_sign = "+" if change >= 0 else ""
            price_str = f"${price:,.2f}" if price >= 1 else f"${price:.4f}"

            text = (
                f"{dec_emoji} *{signal['asset']}* — {decision}\n\n"
                f"💰 Цена: {price_str}\n"
                f"📈 24ч: {change_sign}{change}%\n"
                f"🎯 Уверенность: {conf_pct}%\n"
                f"`{bar}` {conf_pct}%\n"
            )

            if plan == "FREE":
                text += (
                    "\n─────────────────\n"
                    "🔒 _Полная аналитика доступна в PRO_\n"
                    "• Обоснование решения\n"
                    "• Entry / Invalidation\n"
                    "• Deep Intel модули"
                )
            else:
                text += (
                    "\n─────────────────\n"
                    "✅ _PRO-аналитика в мобильном приложении_"
                )

            keyboard = {
                "inline_keyboard": [
                    [{"text": "📊 Другой актив", "callback_data": "signals_list"}],
                    [{"text": "◀️ Меню", "callback_data": "back_menu"}],
                ]
            }

            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            })

        # ── Signals list (pick asset) ──
        elif data == "signals_list":
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "BTC", "callback_data": "sig_BTC"},
                        {"text": "ETH", "callback_data": "sig_ETH"},
                        {"text": "SOL", "callback_data": "sig_SOL"},
                    ],
                    [
                        {"text": "DOGE", "callback_data": "sig_DOGE"},
                        {"text": "XRP", "callback_data": "sig_XRP"},
                        {"text": "AVAX", "callback_data": "sig_AVAX"},
                    ],
                    [{"text": "◀️ Меню", "callback_data": "back_menu"}],
                ]
            }
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": "📊 Выберите актив:",
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            })

        # ── Signal for specific asset ──
        elif data.startswith("sig_"):
            asset = data[4:]
            signal = await _get_latest_signal(asset)
            decision = signal["decision"]
            confidence = signal["confidence"]
            price = signal["price"]
            change = signal["change24h"]

            if decision == "BUY":
                dec_emoji = "🟢"
            elif decision == "SELL":
                dec_emoji = "🔴"
            else:
                dec_emoji = "🟡"

            conf_pct = int(confidence * 100)
            filled = conf_pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            change_sign = "+" if change >= 0 else ""
            price_str = f"${price:,.2f}" if price >= 1 else f"${price:.4f}"

            text = (
                f"{dec_emoji} *{asset}* — {decision}\n\n"
                f"💰 Цена: {price_str}\n"
                f"📈 24ч: {change_sign}{change}%\n"
                f"🎯 Уверенность: {conf_pct}%\n"
                f"`{bar}` {conf_pct}%"
            )

            keyboard = {
                "inline_keyboard": [
                    [{"text": "📊 Другой актив", "callback_data": "signals_list"}],
                    [{"text": "◀️ Меню", "callback_data": "back_menu"}],
                ]
            }

            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            })

        # ── Setup Signals ──
        elif data == "setup_signals":
            linked_user = await _get_user_by_chat(chat_id)
            if linked_user:
                prefs = linked_user.get("preferences", {})
                default_asset = prefs.get("defaultAsset", "BTC")
                notif = prefs.get("notificationSettings", {})
                push_enabled = prefs.get("notifications", True)

                # Format notification status
                status_list = []
                if notif.get("decisionChanges", True):
                    status_list.append("✅ Смена решений")
                else:
                    status_list.append("❌ Смена решений")
                if notif.get("confidenceShifts", True):
                    status_list.append("✅ Сдвиги уверенности")
                else:
                    status_list.append("❌ Сдвиги уверенности")
                if notif.get("keyEvents", True):
                    status_list.append("✅ Ключевые события")
                else:
                    status_list.append("❌ Ключевые события")
                if notif.get("edgeHigh", True):
                    status_list.append("✅ Edge-сигналы")
                else:
                    status_list.append("❌ Edge-сигналы")

                text = (
                    f"⚙️ *Настройка Сигналов*\n\n"
                    f"📊 Актив по умолчанию: *{default_asset}*\n"
                    f"🔔 Push-уведомления: {'✅ Вкл' if push_enabled else '❌ Выкл'}\n\n"
                    f"*Уведомления:*\n" +
                    "\n".join(status_list) +
                    "\n\n─────────────────\n"
                    "Изменить настройки можно в мобильном приложении:\n"
                    "_Profile → Settings → Notifications_"
                )
            else:
                text = (
                    "⚙️ *Настройка Сигналов*\n\n"
                    "Для настройки уведомлений привяжите аккаунт:\n"
                    "_Profile → Connected Apps → Telegram_"
                )

            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": _back_button(),
            })

        # ── Support ──
        elif data == "support":
            _support_mode[chat_id] = True
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": (
                    "🛟 *Поддержка FOMO*\n\n"
                    "Опишите вашу проблему или вопрос одним сообщением.\n"
                    "Мы ответим в ближайшее время.\n\n"
                    "Для отмены: /cancel"
                ),
                "parse_mode": "Markdown",
            })

        # ── Link Account ──
        elif data == "link_account":
            linked_user = await _get_user_by_chat(chat_id)
            if linked_user:
                email = linked_user.get("email", "—")
                plan = linked_user.get("plan", "FREE")
                responses.append({
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": (
                        f"✅ *Аккаунт привязан*\n\n"
                        f"📧 {email}\n"
                        f"📋 План: *{plan}*\n\n"
                        f"Для отвязки: _Profile → Connected Apps → Telegram → Disconnect_"
                    ),
                    "parse_mode": "Markdown",
                    "reply_markup": _back_button(),
                })
            else:
                responses.append({
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": (
                        "🔗 *Привязка аккаунта*\n\n"
                        "Откройте мобильное приложение FOMO:\n"
                        "_Profile → Connected Apps → Telegram → Connect_\n\n"
                        "Приложение сгенерирует код и откроет бота автоматически."
                    ),
                    "parse_mode": "Markdown",
                    "reply_markup": _back_button(),
                })

        # ── My Account ──
        elif data == "my_account":
            linked_user = await _get_user_by_chat(chat_id)
            if linked_user:
                email = linked_user.get("email", "—")
                name = linked_user.get("name", "—")
                member_since = linked_user.get("createdAt")
                since_str = member_since.strftime("%d.%m.%Y") if member_since else "—"
                plan = await _sync_subscription(linked_user, chat_id)

                plan_emoji = "⭐" if plan in ("PRO", "INSTITUTIONAL") else "📋"
                tfa = "✅" if linked_user.get("twoFactorEnabled") else "❌"

                responses.append({
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": (
                        f"👤 *Мой аккаунт*\n\n"
                        f"📧 Email: {email}\n"
                        f"👤 Имя: {name}\n"
                        f"{plan_emoji} План: *{plan}*\n"
                        f"📅 Участник с: {since_str}\n"
                        f"🔐 2FA: {tfa}\n"
                        f"🔗 Telegram: привязан ✅"
                    ),
                    "parse_mode": "Markdown",
                    "reply_markup": _back_button(),
                })
            else:
                responses.append({
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": "❌ Аккаунт не привязан.\n\nПривяжите через приложение FOMO.",
                    "reply_markup": _back_button(),
                })

        # ── PRO Status ──
        elif data == "pro_status":
            linked_user = await _get_user_by_chat(chat_id)
            plan = linked_user.get("plan", "FREE") if linked_user else "FREE"

            if plan in ("PRO", "INSTITUTIONAL"):
                responses.append({
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": (
                        f"⭐ Ваш план: *{plan}*\n\n"
                        f"Все PRO-функции активны:\n"
                        f"• Полная аналитика модулей\n"
                        f"• Edge-возможности\n"
                        f"• Обоснования сигналов\n"
                        f"• Приоритетные уведомления\n"
                        f"• Трек-рекорд + пропущенные\n\n"
                        f"Спасибо за поддержку! 🙏"
                    ),
                    "parse_mode": "Markdown",
                    "reply_markup": _back_button(),
                })
            else:
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🚀 Оформить PRO в приложении", "url": MINIAPP_URL}],
                        [{"text": "◀️ Меню", "callback_data": "back_menu"}],
                    ]
                }
                responses.append({
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": (
                        "📋 Ваш план: *FREE*\n\n"
                        "Что даёт *PRO*:\n"
                        "• Полная аналитика по модулям\n"
                        "• Edge-возможности\n"
                        "• Обоснования решений\n"
                        "• Приоритетные уведомления\n"
                        "• Доступ к Deep Intel\n\n"
                        "💰 *$19/мес* или *$99/год*"
                    ),
                    "parse_mode": "Markdown",
                    "reply_markup": keyboard,
                })

        return responses

    # ─── Regular messages ───
    message = update.get("message")
    if not message:
        return responses

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    user_tg = message.get("from", {})

    # ─── /start link_CODE (must be before plain /start) ───
    if text.startswith("/start") and "link_" in text:
        _support_mode.pop(chat_id, None)
        link_code = text.split("link_")[-1].strip()
        if link_code:
            target_user = await users_col.find_one({
                "telegramLinkCode": link_code,
                "telegramLinkExpires": {"$gt": datetime.utcnow()},
            })
            if target_user:
                await users_col.update_one(
                    {"_id": target_user["_id"]},
                    {"$set": {
                        "telegramChatId": chat_id,
                        "telegramUsername": user_tg.get("username", ""),
                        "authProviders.telegram": True,
                        "updatedAt": datetime.utcnow(),
                    },
                    "$unset": {
                        "telegramLinkCode": 1,
                        "telegramLinkExpires": 1,
                    }}
                )
                email = target_user.get("email", "")
                plan = target_user.get("plan", "FREE")

                # Sync subscription after linking
                updated_user = await users_col.find_one({"_id": target_user["_id"]})
                if updated_user:
                    plan = await _sync_subscription(updated_user, chat_id)

                responses.append({
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": (
                        f"✅ *Telegram привязан!*\n\n"
                        f"📧 Аккаунт: {email}\n"
                        f"📋 План: *{plan}*\n\n"
                        f"Теперь вы будете получать:\n"
                        f"• Уведомления о сигналах\n"
                        f"• Коды верификации\n"
                        f"• Оповещения поддержки"
                    ),
                    "parse_mode": "Markdown",
                    "reply_markup": _main_menu_keyboard(),
                })
            else:
                responses.append({
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": (
                        "❌ Код привязки недействителен или истёк.\n\n"
                        "Сгенерируйте новый в приложении:\n"
                        "_Profile → Connected Apps → Telegram → Connect_"
                    ),
                    "parse_mode": "Markdown",
                    "reply_markup": _back_button(),
                })
        return responses

    # ─── /start support ───
    if text.startswith("/start") and "support" in text:
        _support_mode[chat_id] = True
        responses.append({
            "method": "sendMessage",
            "chat_id": chat_id,
            "text": (
                "🛟 *Поддержка FOMO*\n\n"
                "Опишите вашу проблему — мы поможем.\n\n"
                "Для отмены: /cancel"
            ),
            "parse_mode": "Markdown",
        })
        return responses

    # ─── /start (plain) ───
    if text == "/start":
        _support_mode.pop(chat_id, None)
        linked_user = await _get_user_by_chat(chat_id)
        if linked_user:
            plan = await _sync_subscription(linked_user, chat_id)
            name = linked_user.get("name", user_tg.get("first_name", ""))
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": (
                    f"👋 Привет, *{name}*!\n\n"
                    f"📋 План: *{plan}*\n"
                    f"🔗 Аккаунт привязан ✅\n\n"
                    f"Выберите действие:"
                ),
                "parse_mode": "Markdown",
                "reply_markup": _main_menu_keyboard(),
            })
        else:
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": (
                    "👋 *Добро пожаловать в FOMO!*\n\n"
                    "Decision Layer для крипторынка.\n\n"
                    "Привяжите аккаунт через мобильное приложение, "
                    "чтобы получить доступ ко всем функциям.\n\n"
                    "Выберите действие:"
                ),
                "parse_mode": "Markdown",
                "reply_markup": _main_menu_keyboard(),
            })
        return responses

    # ─── /support ───
    if text == "/support":
        _support_mode[chat_id] = True
        responses.append({
            "method": "sendMessage",
            "chat_id": chat_id,
            "text": (
                "🛟 *Поддержка FOMO*\n\n"
                "Опишите вашу проблему или вопрос одним сообщением.\n"
                "Мы ответим в ближайшее время.\n\n"
                "Для отмены: /cancel"
            ),
            "parse_mode": "Markdown",
        })
        return responses

    # ─── /cancel ───
    if text == "/cancel":
        was_in_support = _support_mode.pop(chat_id, None)
        if was_in_support:
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": "✅ Обращение отменено.",
                "reply_markup": _main_menu_keyboard(),
            })
        else:
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": "✅ Отменено.",
                "reply_markup": _main_menu_keyboard(),
            })
        return responses

    # ─── /menu ───
    if text == "/menu":
        _support_mode.pop(chat_id, None)
        responses.append({
            "method": "sendMessage",
            "chat_id": chat_id,
            "text": "📋 *Меню FOMO*\n\nВыберите действие:",
            "parse_mode": "Markdown",
            "reply_markup": _main_menu_keyboard(),
        })
        return responses

    # ─── /signals ───
    if text == "/signals":
        _support_mode.pop(chat_id, None)
        linked_user = await _get_user_by_chat(chat_id)
        default_asset = "BTC"
        if linked_user:
            default_asset = linked_user.get("preferences", {}).get("defaultAsset", "BTC")

        signal = await _get_latest_signal(default_asset)
        decision = signal["decision"]
        confidence = signal["confidence"]
        price = signal["price"]
        change = signal["change24h"]

        if decision == "BUY":
            dec_emoji = "🟢"
        elif decision == "SELL":
            dec_emoji = "🔴"
        else:
            dec_emoji = "🟡"

        conf_pct = int(confidence * 100)
        filled = conf_pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        change_sign = "+" if change >= 0 else ""
        price_str = f"${price:,.2f}" if price >= 1 else f"${price:.4f}"

        responses.append({
            "method": "sendMessage",
            "chat_id": chat_id,
            "text": (
                f"{dec_emoji} *{signal['asset']}* — {decision}\n\n"
                f"💰 Цена: {price_str}\n"
                f"📈 24ч: {change_sign}{change}%\n"
                f"🎯 Уверенность: {conf_pct}%\n"
                f"`{bar}` {conf_pct}%"
            ),
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "📊 Другой актив", "callback_data": "signals_list"}],
                    [{"text": "◀️ Меню", "callback_data": "back_menu"}],
                ]
            },
        })
        return responses

    # ─── Support mode message ───
    if _support_mode.get(chat_id) and text and not text.startswith("/"):
        linked_user = await _get_user_by_chat(chat_id)
        ticket = {
            "telegram_chat_id": chat_id,
            "telegram_user_id": user_tg.get("id"),
            "telegram_username": user_tg.get("username"),
            "telegram_name": f"{user_tg.get('first_name', '')} {user_tg.get('last_name', '')}".strip(),
            "linked_email": linked_user.get("email") if linked_user else None,
            "linked_plan": linked_user.get("plan") if linked_user else None,
            "message": text,
            "status": "open",
            "created_at": datetime.now(timezone.utc),
        }
        try:
            result = await support_tickets_col.insert_one(ticket)
            ticket_id = str(result.inserted_id)[-6:].upper()
            _support_mode.pop(chat_id, None)
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": (
                    f"✅ *Обращение #{ticket_id} создано*\n\n"
                    f"Мы получили ваш вопрос и ответим в ближайшее время.\n\n"
                    f"Спасибо за обращение!"
                ),
                "parse_mode": "Markdown",
                "reply_markup": _main_menu_keyboard(),
            })
        except Exception as e:
            logger.error(f"Failed to save support ticket: {e}")
            responses.append({
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": "❌ Ошибка сохранения. Попробуйте позже.",
            })
        return responses

    # ─── Unknown message ───
    responses.append({
        "method": "sendMessage",
        "chat_id": chat_id,
        "text": "Используйте меню для навигации:",
        "reply_markup": _main_menu_keyboard(),
    })
    return responses


# ═══════════════════════════════════════════════════
#  SEND HELPERS
# ═══════════════════════════════════════════════════

async def send_telegram_request(method: str, payload: dict):
    """Send a request to Telegram Bot API."""
    import httpx
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(url, json=payload)
            result = resp.json()
            if not result.get("ok"):
                logger.warning(f"Telegram API error: {method} -> {result}")
            return result
        except Exception as e:
            logger.error(f"Telegram API request failed: {method} -> {e}")
            return {"ok": False, "error": str(e)}


async def send_telegram_message(chat_id: int, text: str, parse_mode: str = None, reply_markup: dict = None):
    """Send a message via Telegram Bot API."""
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await send_telegram_request("sendMessage", payload)


async def process_responses(responses: list[dict]):
    """Process all response actions from handle_update."""
    for action in responses:
        method = action.pop("method", "sendMessage")
        await send_telegram_request(method, action)


async def set_bot_commands():
    """Set bot commands list in Telegram."""
    commands = [
        {"command": "start", "description": "Главное меню"},
        {"command": "signals", "description": "Текущие сигналы"},
        {"command": "support", "description": "Написать в поддержку"},
        {"command": "menu", "description": "Показать меню"},
        {"command": "cancel", "description": "Отменить текущее действие"},
    ]
    return await send_telegram_request("setMyCommands", {"commands": commands})


# ═══════════════════════════════════════════════════
#  SUBSCRIPTION SYNC (for auth flow)
# ═══════════════════════════════════════════════════

async def sync_subscription_for_user(user_id: str) -> str:
    """
    Sync subscription for a user based on their telegramChatId.
    Called from auth endpoints during login/refresh.
    Returns the effective plan.
    """
    user = await users_col.find_one({"_id": user_id})
    if not user:
        return "FREE"

    chat_id = user.get("telegramChatId")
    if not chat_id:
        return user.get("plan", "FREE")

    return await _sync_subscription(user, chat_id)


async def update_user_plan_by_chat(chat_id: int, new_plan: str) -> bool:
    """
    Update plan for all users linked to a Telegram chatId.
    Called when MiniApp reports a subscription change.
    """
    if new_plan not in PLAN_RANK:
        return False

    new_rank = PLAN_RANK[new_plan]

    cursor = users_col.find({"telegramChatId": chat_id})
    updated = 0

    async for user in cursor:
        current_plan = user.get("plan", "FREE")
        current_rank = PLAN_RANK.get(current_plan, 0)
        if new_rank > current_rank:
            await users_col.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "plan": new_plan,
                    "subscription.plan": new_plan,
                    "subscription.status": "ACTIVE",
                    "access.fullSignals": new_plan != "FREE",
                    "access.fullIntel": new_plan != "FREE",
                    "access.edge": new_plan != "FREE",
                    "updatedAt": datetime.utcnow(),
                }}
            )
            updated += 1
            logger.info(f"Plan updated via MiniApp sync: {user.get('email')} {current_plan} -> {new_plan}")

    return updated > 0
