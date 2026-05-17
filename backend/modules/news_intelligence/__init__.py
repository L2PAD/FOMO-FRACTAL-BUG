"""
News Intelligence Layer
========================

Crypto Intelligence News Engine for FOMO Platform.

Modules:
- ingestion: Source fetching and crawling
- parsers: Article content extraction
- normalizers: Text cleaning and standardization
- embeddings: MiniLM vector generation
- clustering: Event detection and grouping
- extraction: Fact and entity extraction (GPT-4o-mini)
- linking: Entity resolution to platform objects
- synthesis: AI story generation (GPT-5.2)
- ranking: Event scoring and feed ordering
- api: REST endpoints
- jobs: Background tasks
- storage: Database operations
"""

from .api.routes import router as news_intelligence_router

__all__ = ["news_intelligence_router"]
