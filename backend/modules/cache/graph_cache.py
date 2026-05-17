"""
Graph cache stub - no-op cache layer.
"""

class GraphCache:
    def __init__(self, db=None):
        pass
    
    async def get(self, key):
        return None
    
    async def set(self, key, value, ttl=3600):
        pass
    
    async def invalidate(self, key=None):
        pass
    
    async def get_stats(self):
        return {"hits": 0, "misses": 0, "size": 0}
