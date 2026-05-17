"""
Gateway layer — transparent reverse proxies to side-car subsystems.

Each gateway module is a FastAPI APIRouter that forwards a fixed set of
URL prefixes to a single upstream host. Gateways are intentionally thin:
no business logic, no DB access, only header/body passthrough.

Conventions:
- Gateways live ONLY here (never inside server.py).
- Prefixes are explicit (no wildcard catch-alls).
- Auth / cookies / x-forwarded-* are propagated.
- Timeouts are conservative for heavy TA endpoints (120s).
- Errors from upstream are passed through, not masked.
"""
