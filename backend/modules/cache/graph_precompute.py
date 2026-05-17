"""
Graph precompute stub - no-op precompute layer.
"""

class GraphPrecomputeService:
    def __init__(self, db=None):
        pass
    
    async def get_precomputed(self, entity_id):
        return None
    
    async def precompute(self, entity_id):
        pass
    
    async def get_stats(self):
        return {"total": 0, "fresh": 0, "stale": 0}

def get_precompute_service(db=None):
    return GraphPrecomputeService(db)
