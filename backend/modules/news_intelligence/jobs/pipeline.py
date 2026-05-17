"""
News Intelligence Pipeline Orchestrator
========================================

Coordinates all pipeline stages: fetch → normalize → embed → cluster → extract → synthesize → rank
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone

from ..ingestion import NewsFetcher, get_active_sources
from ..normalizers import ArticleNormalizer
from ..embeddings import ArticleEmbedder
from ..clustering import EventClusteringEngine
from ..extraction import EventFactProcessor
from ..synthesis import EventStorySynthesizer
from ..ranking import EventRanker

logger = logging.getLogger(__name__)


class NewsIntelligencePipeline:
    """Orchestrates the full news intelligence pipeline."""
    
    def __init__(self, db):
        self.db = db
        self.normalizer = ArticleNormalizer(db)
        self.embedder = ArticleEmbedder(db)
        self.clustering = EventClusteringEngine(db)
        self.fact_processor = EventFactProcessor(db)
        self.story_synthesizer = EventStorySynthesizer(db)
        self.ranker = EventRanker(db)
    
    async def run_full_pipeline(self, fetch_limit: int = 50) -> Dict[str, Any]:
        """Run the complete pipeline."""
        start_time = datetime.now(timezone.utc)
        results = {
            "ok": True,
            "started_at": start_time.isoformat(),
            "stages": {}
        }
        
        try:
            # Stage 1: Fetch new articles
            logger.info("[Pipeline] Stage 1: Fetching articles...")
            async with NewsFetcher(self.db) as fetcher:
                sources = get_active_sources()
                fetch_result = await fetcher.fetch_all_sources(sources)
                results["stages"]["fetch"] = fetch_result
            
            # Stage 2: Normalize articles
            logger.info("[Pipeline] Stage 2: Normalizing articles...")
            normalize_result = await self.normalizer.process_pending_articles(limit=fetch_limit)
            results["stages"]["normalize"] = normalize_result
            
            # Stage 3: Generate embeddings
            logger.info("[Pipeline] Stage 3: Generating embeddings...")
            embed_result = await self.embedder.embed_pending_articles(limit=fetch_limit)
            results["stages"]["embed"] = embed_result
            
            # Stage 4: Cluster into events
            logger.info("[Pipeline] Stage 4: Clustering events...")
            cluster_result = await self.clustering.process_pending_articles(limit=fetch_limit)
            results["stages"]["cluster"] = cluster_result
            
            # Stage 5: Extract facts (for confirmed events)
            logger.info("[Pipeline] Stage 5: Extracting facts...")
            extract_result = await self.fact_processor.process_pending_events(limit=10)
            results["stages"]["extract"] = extract_result
            
            # Stage 6: Synthesize stories (for confirmed events)
            logger.info("[Pipeline] Stage 6: Synthesizing stories...")
            synthesize_result = await self.story_synthesizer.process_pending_events(limit=5)
            results["stages"]["synthesize"] = synthesize_result
            
            # Stage 7: Update rankings
            logger.info("[Pipeline] Stage 7: Updating rankings...")
            rank_result = await self.ranker.update_all_scores()
            results["stages"]["rank"] = rank_result
            
            # Calculate duration
            end_time = datetime.now(timezone.utc)
            results["completed_at"] = end_time.isoformat()
            results["duration_sec"] = (end_time - start_time).total_seconds()
            
            logger.info(f"[Pipeline] Complete in {results['duration_sec']:.2f}s")
            
        except Exception as e:
            results["ok"] = False
            results["error"] = str(e)
            logger.error(f"[Pipeline] Error: {e}")
        
        return results
    
    async def run_fetch_only(self) -> Dict[str, Any]:
        """Run only the fetch stage."""
        async with NewsFetcher(self.db) as fetcher:
            sources = get_active_sources()
            return await fetcher.fetch_all_sources(sources)
    
    async def run_process_only(self, limit: int = 50) -> Dict[str, Any]:
        """Run processing stages without fetching."""
        results = {}
        
        results["normalize"] = await self.normalizer.process_pending_articles(limit)
        results["embed"] = await self.embedder.embed_pending_articles(limit)
        results["cluster"] = await self.clustering.process_pending_articles(limit)
        
        return results
    
    async def run_synthesis_only(self, limit: int = 5) -> Dict[str, Any]:
        """Run synthesis for confirmed events."""
        results = {}
        
        results["extract"] = await self.fact_processor.process_pending_events(limit)
        results["synthesize"] = await self.story_synthesizer.process_pending_events(limit)
        results["rank"] = await self.ranker.update_all_scores()
        
        return results
    
    async def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        stats = {
            "raw_articles": await self.db.raw_articles.count_documents({}),
            "raw_pending": await self.db.raw_articles.count_documents({"status": "pending"}),
            "normalized_articles": await self.db.normalized_articles.count_documents({}),
            "articles_with_embeddings": await self.db.normalized_articles.count_documents({"embedding": {"$ne": None}}),
            "events_total": await self.db.news_events.count_documents({}),
            "events_candidate": await self.db.news_events.count_documents({"status": "candidate"}),
            "events_developing": await self.db.news_events.count_documents({"status": "developing"}),
            "events_confirmed": await self.db.news_events.count_documents({"status": "confirmed"}),
            "events_with_story": await self.db.news_events.count_documents({"story_en": {"$ne": None}}),
            "sources_active": len(get_active_sources())
        }
        
        return stats
