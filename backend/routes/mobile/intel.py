"""Intel & Deep Intel routes."""
from fastapi import APIRouter, Query
import services.intel.intel_service as intel_service

router = APIRouter()


@router.get("/intel")
async def get_intel(asset: str = Query(default="BTC")):
    return await intel_service.get_intel_overview(asset)


@router.get("/intel/exchange")
async def get_intel_exchange(asset: str = Query(default="BTC")):
    return await intel_service.get_exchange_intel(asset)


@router.get("/intel/onchain")
async def get_intel_onchain(asset: str = Query(default="BTC")):
    return await intel_service.get_onchain_intel(asset)


@router.get("/intel/sentiment")
async def get_intel_sentiment(asset: str = Query(default="BTC")):
    return await intel_service.get_sentiment_intel(asset)


@router.get("/intel/fractal")
async def get_intel_fractal(asset: str = Query(default="BTC")):
    return await intel_service.get_fractal_intel(asset)
