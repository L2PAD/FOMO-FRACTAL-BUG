"""
Telegram Intel - Background Scheduler
Runs periodic scraping + metrics computation pipeline.
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, db, interval_minutes: int = 60):
        self.db = db
        self.interval = interval_minutes * 60
        self._task = None
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Scheduler started: pipeline every {self.interval // 60} min")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _loop(self):
        while self._running:
            try:
                await self._run_pipeline()
            except Exception as e:
                logger.error(f"Scheduler pipeline error: {e}")
            await asyncio.sleep(self.interval)

    async def _run_pipeline(self):
        logger.info("Scheduler: starting pipeline run...")
        now = datetime.now(timezone.utc)

        # Step 1: Fetch channel info + messages via MTProto
        try:
            from ..api.admin import get_mtproto_client, MTPROTO_AVAILABLE
            if not MTPROTO_AVAILABLE:
                logger.warning("Scheduler: MTProto not available, skipping scrape")
            else:
                client = get_mtproto_client()
                if not await client.is_connected():
                    connected = await client.connect(db=self.db)
                    if not connected:
                        logger.warning("Scheduler: cannot connect to Telegram")
                        await self._run_metrics()
                        return

                channels = await self.db.tg_channel_states.find(
                    {"stage": {"$in": ["QUALIFIED", "CANDIDATE"]}},
                    {"_id": 0, "username": 1}
                ).to_list(200)

                scraped = 0
                for ch in channels:
                    username = ch["username"]
                    try:
                        info = await client.get_channel_info(username)
                        if info and "error" not in info:
                            await self.db.tg_channel_states.update_one(
                                {"username": username},
                                {"$set": {
                                    "participantsCount": info["participantsCount"],
                                    "title": info["title"],
                                    "lastMtprotoFetch": now,
                                    "updatedAt": now,
                                }}
                            )

                            try:
                                from ..services.members_history import write_members_history
                                await write_members_history(self.db, username, info["participantsCount"])
                            except Exception:
                                pass

                            msgs = await client.get_channel_messages(username, limit=50, db=self.db)
                            if msgs:
                                for msg in msgs:
                                    d = msg.get("date")
                                    if isinstance(d, str):
                                        try:
                                            msg["date"] = datetime.fromisoformat(d)
                                        except Exception:
                                            pass
                                    await self.db.tg_posts.update_one(
                                        {"username": username, "messageId": msg["messageId"]},
                                        {"$set": {**msg, "username": username, "updatedAt": now},
                                         "$setOnInsert": {"createdAt": now}},
                                        upsert=True,
                                    )
                            scraped += 1
                    except Exception as e:
                        logger.warning(f"Scheduler: scrape error for @{username}: {e}")
                    await asyncio.sleep(2)
                logger.info(f"Scheduler: scraped {scraped}/{len(channels)} channels")
        except Exception as e:
            logger.error(f"Scheduler: scrape phase error: {e}")

        # Step 2: Recompute metrics
        await self._run_metrics()
        logger.info("Scheduler: pipeline complete")

    async def _run_metrics(self):
        try:
            from ..services.metrics import compute_channel_metrics
            channels = await self.db.tg_channel_states.find(
                {}, {"_id": 0, "username": 1}
            ).to_list(200)

            computed = 0
            for ch in channels:
                try:
                    await compute_channel_metrics(self.db, ch["username"])
                    computed += 1
                except Exception as e:
                    logger.warning(f"Scheduler: metrics error for @{ch['username']}: {e}")
            logger.info(f"Scheduler: computed metrics for {computed}/{len(channels)} channels")
        except Exception as e:
            logger.error(f"Scheduler: metrics phase error: {e}")


async def start_scheduler(db, interval_minutes: int = 60):
    scheduler = Scheduler(db, interval_minutes)
    await scheduler.start()
    return scheduler


async def stop_scheduler(scheduler):
    if scheduler and isinstance(scheduler, Scheduler):
        await scheduler.stop()
