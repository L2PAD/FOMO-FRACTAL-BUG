from .routes import router as intel_router
from .routes_admin import router as admin_router
from .routes_engine import router as engine_router

__all__ = ['intel_router', 'admin_router', 'engine_router']
