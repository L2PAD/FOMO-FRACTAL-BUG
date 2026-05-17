"""
Redis client stub - no-op cache layer.
Knowledge graph works without Redis, just bypasses cache.
"""

def is_redis_available():
    return False

async def cache_get(key):
    return None

async def cache_set(key, value, ttl=3600):
    pass

async def cache_delete(key):
    pass
