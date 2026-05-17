"""Master Mobile Router — mounts all sub-routers."""
from fastapi import APIRouter
from . import assets, home, feed, edge, intel, profile, push, missed, trading, subscription, notifications, fractal, sentiment, signals, behavior, brain, portfolio

mobile_router = APIRouter(prefix="/api/mobile", tags=["mobile"])

mobile_router.include_router(assets.router)
mobile_router.include_router(home.router)
mobile_router.include_router(feed.router)
mobile_router.include_router(edge.router)
mobile_router.include_router(intel.router)
mobile_router.include_router(profile.router)
mobile_router.include_router(push.router)
mobile_router.include_router(missed.router)
mobile_router.include_router(trading.router)
mobile_router.include_router(subscription.router)
mobile_router.include_router(notifications.router)
mobile_router.include_router(fractal.router)
mobile_router.include_router(sentiment.router)
mobile_router.include_router(signals.router)
mobile_router.include_router(behavior.router)
mobile_router.include_router(brain.router)
mobile_router.include_router(portfolio.router)
