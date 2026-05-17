"""
Fractal Sidecar Proxy
======================
Transparent proxy from FastAPI (Python) to the Node.js sidecar that
hosts the REAL Fractal v2.1 engine (cosine-similarity, replay/synthetic
/hybrid, BTC × SPX overlay).

This router is mounted **before** all legacy DB-backed handlers in
server.py so the real engine wins on overlapping routes.
"""

from __future__ import annotations

import os
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["fractal_sidecar_proxy"])

_NODE_SIDECAR_URL = os.environ.get("NODE_SIDECAR_URL", "http://127.0.0.1:8003")
_client = httpx.Client(timeout=httpx.Timeout(30.0, connect=3.0))


def _proxy(request: Request):
    target = f"{_NODE_SIDECAR_URL}{request.url.path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    try:
        r = _client.request(request.method, target)
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": "node_sidecar_unreachable",
                "detail": str(e),
                "upstream": target,
            },
        )
    try:
        return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception:
        return JSONResponse(
            status_code=r.status_code or 502,
            content={"ok": False, "error": "node_sidecar_bad_json",
                     "upstream_status": r.status_code, "raw": r.text[:512]},
        )


# ── Fractal v2.1 core engine ─────────────────────────────────────────
@router.get("/fractal/v2.1/overlay")
@router.get("/fractal/v2.1/focus-pack")
@router.get("/fractal/v2.1/chart")
@router.get("/fractal/v2.1/terminal")
@router.get("/fractal/v2.1/replay-pack")
@router.get("/fractal/v2.1/multi-signal")
@router.get("/fractal/v2.1/regime")
@router.get("/fractal/v2.1/signal")
def fractal_v21(request: Request):
    return _proxy(request)


# ── SPX & DXY (replay / synthetic / hybrid / horizons) ────────────────
@router.get("/fractal/spx")
@router.get("/fractal/dxy")
@router.get("/fractal/spx/replay")
@router.get("/fractal/dxy/replay")
@router.get("/fractal/spx/replay/matches")
@router.get("/fractal/dxy/replay/matches")
@router.get("/fractal/spx/synthetic")
@router.get("/fractal/dxy/synthetic")
@router.get("/fractal/spx/hybrid")
@router.get("/fractal/dxy/hybrid")
@router.get("/fractal/spx/horizons")
@router.get("/fractal/dxy/horizons")
@router.get("/fractal/spx/debug-similarity")
@router.get("/fractal/dxy/debug-similarity")
@router.get("/fractal/spx/audit")
@router.get("/fractal/dxy/audit")
def fractal_scope(request: Request):
    return _proxy(request)


# ── BTC × SPX cross-asset overlay ────────────────────────────────────
@router.get("/overlay/coeffs")
@router.get("/overlay/adjusted-path")
@router.get("/overlay/explain")
def btc_overlay(request: Request):
    return _proxy(request)


# ── BTC v2.1 proxied terminal/focus pack ────────────────────────────
@router.get("/btc/v2.1/terminal")
@router.get("/btc/v2.1/focus-pack")
@router.get("/btc/v2.1/chart")
@router.get("/btc/v2.1/replay-pack")
@router.get("/btc/v2.1/multi-signal")
@router.get("/btc/v2.1/regime")
def btc_v21(request: Request):
    return _proxy(request)


# ── Brain forecast / cross-asset (real engine on sidecar) ────────────
@router.get("/brain/v2/forecast")
@router.get("/brain/v2/cross-asset")
@router.get("/brain/v2/features")
def brain_v2(request: Request):
    return _proxy(request)


# ── Health bridge ────────────────────────────────────────────────────
@router.get("/sidecar/healthz")
def sidecar_health(request: Request):
    return _proxy(request)
