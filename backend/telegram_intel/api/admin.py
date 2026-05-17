"""
Telegram Intel - Admin API Routes (MTProto, Ingestion, Seeds)
Wires up telegram_lite engine for real Telegram data scraping.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger(__name__)

# Module availability flags
MTPROTO_AVAILABLE = False
MEMBERS_HISTORY_LOADED = False
SEEDS_AVAILABLE = False

try:
    from telegram_lite.mtproto_client import MTProtoClient, get_session_state
    MTPROTO_AVAILABLE = True
    logger.info("MTProto client loaded")
except ImportError as e:
    logger.warning(f"MTProto client not available: {e}")

try:
    from telegram_lite.members_history import write_members_history, calculate_growth, get_members_history
    MEMBERS_HISTORY_LOADED = True
    logger.info("Members history module loaded")
except ImportError as e:
    logger.warning(f"Members history not available: {e}")

try:
    from telegram_lite.seeds import import_seeds
    SEEDS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Seeds not available: {e}")


def get_mtproto_client() -> MTProtoClient:
    return MTProtoClient.get_instance()


AVATAR_DIR = Path("/app/backend/public/tg/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)


def normalize_username(raw: str) -> str:
    return raw.lower().replace("@", "").replace("https://t.me/", "").replace("t.me/", "").split("/")[0].split("?")[0].strip()


def create_admin_router(module) -> APIRouter:
    router = APIRouter(prefix="/api/telegram-intel", tags=["telegram-intel-admin"])

    async def get_db():
        return module.db

    # ─── MTProto Status / Connect / Reconnect ─────────────────────────
    @router.get("/admin/mtproto/status")
    async def mtproto_status():
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "available": False, "message": "MTProto client not installed"}
        try:
            client = get_mtproto_client()
            connected = await client.is_connected()
            return {"ok": True, "available": True, "connected": connected, "state": get_session_state()}
        except Exception as e:
            return {"ok": False, "available": True, "connected": False, "error": str(e)}

    @router.post("/admin/mtproto/connect")
    async def mtproto_connect():
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "error": "MTProto not available"}
        try:
            db = await get_db()
            client = get_mtproto_client()
            success = await client.connect(db=db)
            if success:
                health = await client.health_check()
                return {"ok": True, "status": "connected", **health}
            return {"ok": False, "status": "not_authorized", "message": "Session may be expired"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @router.get("/admin/mtproto/health")
    async def mtproto_health():
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "connected": False, "authorized": False, "error": "MTProto not available"}
        try:
            client = get_mtproto_client()
            health = await client.health_check()
            return {"ok": True, **health}
        except Exception as e:
            return {"ok": False, "connected": False, "error": str(e)}

    @router.post("/admin/mtproto/reconnect")
    async def mtproto_reconnect():
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "error": "MTProto not available"}
        try:
            client = get_mtproto_client()
            await client.disconnect()
            success = await client.connect(retry_count=3)
            health = await client.health_check()
            return {"ok": success, "reconnected": success, **health}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Channel Fetch via MTProto ────────────────────────────────────
    @router.get("/admin/mtproto/fetch/{username}")
    async def mtproto_fetch_channel(username: str):
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "error": "MTProto not available"}
        db = await get_db()
        cu = normalize_username(username)
        try:
            client = get_mtproto_client()
            if not await client.is_connected():
                await client.connect(db=db)

            info = await client.get_channel_info(cu)
            if not info or "error" in info:
                return {"ok": False, "data": info}

            now = datetime.now(timezone.utc)
            await db.tg_channel_states.update_one(
                {"username": info["username"]},
                {
                    "$set": {
                        "username": info["username"],
                        "title": info["title"],
                        "about": info.get("about", ""),
                        "participantsCount": info["participantsCount"],
                        "isChannel": info["isChannel"],
                        "lastMtprotoFetch": now,
                        "updatedAt": now,
                    },
                    "$setOnInsert": {"createdAt": now, "stage": "QUALIFIED"},
                },
                upsert=True,
            )

            if MEMBERS_HISTORY_LOADED:
                await write_members_history(db, info["username"], info["participantsCount"])

            # Download avatar
            avatar_url = None
            try:
                avatar_url = await client.download_profile_photo(info["username"])
                if avatar_url:
                    await db.tg_channel_states.update_one(
                        {"username": info["username"]},
                        {"$set": {"avatarUrl": avatar_url}},
                    )
            except Exception as ae:
                logger.warning(f"Avatar download failed: {ae}")

            return {
                "ok": True,
                "source": "mtproto",
                "data": info,
                "savedToDb": True,
                "membersHistoryWritten": MEMBERS_HISTORY_LOADED,
                "avatarUrl": avatar_url,
            }
        except Exception as e:
            logger.error(f"MTProto fetch error: {e}")
            return {"ok": False, "error": str(e)}

    # ─── Fetch Messages ───────────────────────────────────────────────
    @router.get("/admin/mtproto/messages/{username}")
    async def mtproto_fetch_messages(username: str, limit: int = 100, download_media: bool = False):
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "error": "MTProto not available"}
        db = await get_db()
        cu = normalize_username(username)
        try:
            client = get_mtproto_client()
            if not await client.is_connected():
                await client.connect(db=db)

            messages = await client.get_channel_messages(cu, limit=min(limit, 500), download_media=download_media, db=db)
            if messages is None:
                return {"ok": False, "error": "Failed to fetch messages"}

            # Save to DB
            saved = 0
            now = datetime.now(timezone.utc)
            for msg in messages:
                # Ensure date is datetime, not string
                d = msg.get("date")
                if isinstance(d, str):
                    try:
                        from datetime import datetime as dt_cls
                        msg["date"] = dt_cls.fromisoformat(d)
                    except Exception:
                        pass
                await db.tg_posts.update_one(
                    {"username": cu, "messageId": msg["messageId"]},
                    {
                        "$set": {**msg, "username": cu, "updatedAt": now},
                        "$setOnInsert": {"createdAt": now},
                    },
                    upsert=True,
                )
                saved += 1

            return {"ok": True, "username": cu, "fetched": len(messages), "savedToDb": saved}
        except Exception as e:
            logger.error(f"MTProto messages error: {e}")
            return {"ok": False, "error": str(e)}

    # ─── Seeds Import ─────────────────────────────────────────────────
    @router.post("/admin/seeds/import")
    async def seeds_import(body: dict = None):
        db = await get_db()
        if db is None:
            return {"ok": False, "error": "DB not connected"}
        try:
            usernames = (body or {}).get("usernames", [])
            if not usernames:
                return {"ok": False, "error": "usernames array required"}
            if SEEDS_AVAILABLE:
                result = await import_seeds(db, usernames)
                return {"ok": True, **result}
            else:
                # Manual insert
                now = datetime.now(timezone.utc)
                inserted = 0
                for u in usernames:
                    cu = normalize_username(u)
                    if not cu:
                        continue
                    r = await db.tg_channel_states.update_one(
                        {"username": cu},
                        {"$setOnInsert": {"username": cu, "stage": "CANDIDATE", "createdAt": now}, "$set": {"updatedAt": now}},
                        upsert=True,
                    )
                    if r.upserted_id:
                        inserted += 1
                return {"ok": True, "inserted": inserted}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    DEFAULT_SEEDS = [
        "incrypted", "cryptodep", "taborsky_channel", "forklog",
        "durov", "bitcoinmagazine", "defillama", "theblock_co",
        "CryptoNewsHerald", "coin_post", "RuCryptoNews",
    ]

    @router.post("/admin/seeds/import/default")
    async def seeds_import_default():
        db = await get_db()
        if db is None:
            return {"ok": False, "error": "DB not connected"}
        try:
            if SEEDS_AVAILABLE:
                result = await import_seeds(db, DEFAULT_SEEDS)
                return {"ok": True, "seeds": DEFAULT_SEEDS, **result}
            now = datetime.now(timezone.utc)
            inserted = 0
            for u in DEFAULT_SEEDS:
                r = await db.tg_channel_states.update_one(
                    {"username": u},
                    {"$setOnInsert": {"username": u, "stage": "CANDIDATE", "createdAt": now}, "$set": {"updatedAt": now}},
                    upsert=True,
                )
                if r.upserted_id:
                    inserted += 1
            return {"ok": True, "seeds": DEFAULT_SEEDS, "inserted": inserted}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Full Pipeline: seed + fetch + messages ───────────────────────
    @router.post("/admin/pipeline/run")
    async def pipeline_run(body: dict = None):
        """Run full pipeline: seed channels -> fetch info -> fetch messages"""
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "error": "MTProto not available"}
        db = await get_db()
        try:
            usernames = (body or {}).get("usernames", DEFAULT_SEEDS)
            limit_msgs = (body or {}).get("messagesLimit", 50)

            client = get_mtproto_client()
            if not await client.is_connected():
                connected = await client.connect(db=db)
                if not connected:
                    return {"ok": False, "error": "Cannot connect to Telegram"}

            results = []
            for u in usernames:
                cu = normalize_username(u)
                if not cu:
                    continue

                step = {"username": cu, "info": False, "messages": 0, "error": None}

                # Fetch channel info
                info = await client.get_channel_info(cu)
                if info and "error" not in info:
                    now = datetime.now(timezone.utc)
                    await db.tg_channel_states.update_one(
                        {"username": cu},
                        {
                            "$set": {
                                "username": cu, "title": info["title"],
                                "about": info.get("about", ""),
                                "participantsCount": info["participantsCount"],
                                "isChannel": info["isChannel"],
                                "lastMtprotoFetch": now, "updatedAt": now,
                                "stage": "QUALIFIED",
                            },
                            "$setOnInsert": {"createdAt": now},
                        },
                        upsert=True,
                    )
                    step["info"] = True

                    if MEMBERS_HISTORY_LOADED:
                        try:
                            await write_members_history(db, cu, info["participantsCount"])
                        except Exception:
                            pass

                    # Download avatar
                    try:
                        avatar_url = await client.download_profile_photo(cu)
                        if avatar_url:
                            await db.tg_channel_states.update_one({"username": cu}, {"$set": {"avatarUrl": avatar_url}})
                    except Exception:
                        pass

                    # Fetch messages
                    msgs = await client.get_channel_messages(cu, limit=min(limit_msgs, 200), db=db)
                    if msgs:
                        for msg in msgs:
                            d = msg.get("date")
                            if isinstance(d, str):
                                try:
                                    msg["date"] = datetime.fromisoformat(d)
                                except Exception:
                                    pass
                            await db.tg_posts.update_one(
                                {"username": cu, "messageId": msg["messageId"]},
                                {"$set": {**msg, "username": cu, "updatedAt": now}, "$setOnInsert": {"createdAt": now}},
                                upsert=True,
                            )
                        step["messages"] = len(msgs)
                else:
                    step["error"] = info.get("error") if info else "no_response"

                results.append(step)

            ok_count = sum(1 for r in results if r["info"])
            return {"ok": True, "processed": len(results), "successful": ok_count, "results": results}
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return {"ok": False, "error": str(e)}

    # ─── Avatars Static Serve ─────────────────────────────────────────
    @router.get("/avatars/{username}.jpg")
    async def get_avatar(username: str):
        cu = normalize_username(username)
        path = AVATAR_DIR / f"{cu}.jpg"
        if path.exists():
            return FileResponse(path, media_type="image/jpeg")
        return JSONResponse(status_code=404, content={"error": "Avatar not found"})

    # ─── Media Static Serve ───────────────────────────────────────────
    @router.get("/media/{username}/{filename}")
    async def get_media(username: str, filename: str):
        cu = normalize_username(username)
        media_path = Path("/app/backend/public/tg/media") / cu / filename
        if media_path.exists():
            mime = "image/jpeg" if filename.endswith(".jpg") else "video/mp4" if filename.endswith(".mp4") else "application/octet-stream"
            return FileResponse(media_path, media_type=mime)
        return JSONResponse(status_code=404, content={"error": "Media not found"})

    # ─── Channel Growth (requires members_history) ────────────────────
    @router.get("/channel/{username}/growth")
    async def channel_growth(username: str):
        if not MEMBERS_HISTORY_LOADED:
            return {"ok": False, "error": "Members history not available"}
        db = await get_db()
        cu = normalize_username(username)
        try:
            growth = await calculate_growth(db, cu)
            history = await get_members_history(db, cu, days=30)
            return {"ok": True, "username": cu, "growth": growth, "history": history, "hasData": growth.get("currentMembers") is not None}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return router
