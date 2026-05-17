"""
Embedding Generator
===================

Generates embeddings using sentence-transformers MiniLM for event clustering.
"""

import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Lazy load to avoid startup delay
_model = None


def get_embedding_model():
    """Lazy load sentence transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("[Embeddings] MiniLM model loaded")
        except Exception as e:
            logger.error(f"[Embeddings] Failed to load model: {e}")
    return _model


class EmbeddingGenerator:
    """Generates embeddings for articles and events."""
    
    def __init__(self):
        self.model = None
    
    def _ensure_model(self):
        """Ensure model is loaded."""
        if self.model is None:
            self.model = get_embedding_model()
        return self.model is not None
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text."""
        if not self._ensure_model():
            return None
        
        if not text or len(text.strip()) < 10:
            return None
        
        try:
            # Truncate to reasonable length
            text = text[:2000]
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"[Embeddings] Error generating embedding: {e}")
            return None
    
    def generate_event_text(self, title: str, summary: str, entities: List[str], 
                           assets: List[str], event_hints: List[str]) -> str:
        """Generate compact text for event embedding."""
        parts = [title]
        
        if summary:
            parts.append(summary[:200])
        
        if entities:
            parts.append(f"Entities: {', '.join(entities[:5])}")
        
        if assets:
            parts.append(f"Assets: {', '.join(assets[:5])}")
        
        if event_hints:
            parts.append(f"Events: {', '.join(event_hints[:3])}")
        
        return " ".join(parts)
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            a = np.array(vec1)
            b = np.array(vec2)
            
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return float(dot_product / (norm_a * norm_b))
        except Exception as e:
            logger.error(f"[Embeddings] Similarity error: {e}")
            return 0.0
    
    def calculate_centroid(self, embeddings: List[List[float]]) -> Optional[List[float]]:
        """Calculate centroid of multiple embeddings."""
        if not embeddings:
            return None
        
        try:
            arr = np.array(embeddings)
            centroid = np.mean(arr, axis=0)
            return centroid.tolist()
        except Exception as e:
            logger.error(f"[Embeddings] Centroid error: {e}")
            return None
    
    def find_most_similar(self, query_embedding: List[float], 
                         embeddings: List[List[float]], 
                         threshold: float = 0.7) -> List[tuple]:
        """Find embeddings above similarity threshold."""
        results = []
        
        for i, emb in enumerate(embeddings):
            sim = self.cosine_similarity(query_embedding, emb)
            if sim >= threshold:
                results.append((i, sim))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results


class ArticleEmbedder:
    """Handles article embedding operations with batch processing."""
    
    BATCH_SIZE = 20  # Process 20 articles at once
    
    def __init__(self, db):
        self.db = db
        self.generator = EmbeddingGenerator()
    
    async def embed_article(self, article_id: str) -> bool:
        """Generate and store embedding for a single article."""
        article = await self.db.normalized_articles.find_one({"id": article_id})
        if not article:
            return False
        
        if article.get("embedding"):
            return True  # Already embedded
        
        # Generate event text
        event_text = self.generator.generate_event_text(
            title=article.get("title", ""),
            summary=article.get("summary", ""),
            entities=article.get("entities", []),
            assets=article.get("assets", []),
            event_hints=article.get("event_hints", [])
        )
        
        embedding = self.generator.generate_embedding(event_text)
        
        if embedding:
            await self.db.normalized_articles.update_one(
                {"id": article_id},
                {"$set": {"embedding": embedding}}
            )
            return True
        
        return False
    
    def _batch_generate_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for a batch of texts."""
        if not self.generator._ensure_model():
            return [None] * len(texts)
        
        try:
            # Filter valid texts
            valid_texts = []
            valid_indices = []
            
            for i, text in enumerate(texts):
                if text and len(text.strip()) >= 10:
                    valid_texts.append(text[:2000])
                    valid_indices.append(i)
            
            if not valid_texts:
                return [None] * len(texts)
            
            # Batch encode
            embeddings = self.generator.model.encode(valid_texts, convert_to_numpy=True)
            
            # Map back to original indices
            result = [None] * len(texts)
            for idx, emb in zip(valid_indices, embeddings):
                result[idx] = emb.tolist()
            
            return result
            
        except Exception as e:
            logger.error(f"[Embeddings] Batch error: {e}")
            return [None] * len(texts)
    
    async def embed_pending_articles(self, limit: int = 100) -> dict:
        """Embed articles using batch processing for efficiency."""
        results = {
            "processed": 0,
            "embedded": 0,
            "batches": 0,
            "errors": 0
        }
        
        # Collect articles without embeddings
        cursor = self.db.normalized_articles.find({
            "embedding": None,
            "is_duplicate": False
        }).limit(limit)
        
        articles = []
        async for article in cursor:
            articles.append(article)
        
        if not articles:
            return results
        
        results["processed"] = len(articles)
        
        # Process in batches
        for i in range(0, len(articles), self.BATCH_SIZE):
            batch = articles[i:i + self.BATCH_SIZE]
            results["batches"] += 1
            
            # Generate texts for batch
            texts = []
            for article in batch:
                event_text = self.generator.generate_event_text(
                    title=article.get("title", ""),
                    summary=article.get("summary", ""),
                    entities=article.get("entities", []),
                    assets=article.get("assets", []),
                    event_hints=article.get("event_hints", [])
                )
                texts.append(event_text)
            
            # Batch embed
            embeddings = self._batch_generate_embeddings(texts)
            
            # Store results
            for article, embedding in zip(batch, embeddings):
                if embedding:
                    await self.db.normalized_articles.update_one(
                        {"id": article["id"]},
                        {"$set": {"embedding": embedding}}
                    )
                    results["embedded"] += 1
                else:
                    results["errors"] += 1
        
        logger.info(f"[Embeddings] Batch processed {results['processed']} articles in {results['batches']} batches")
        
        return results
