"""
ResQAI - Embedding Service
Generates vector embeddings for text and documents using OpenAI text-embedding-3-large.
Supports batch embedding, caching, and dimension reduction.
"""

import asyncio
import hashlib
from typing import List, Optional

from loguru import logger

from app.config import settings
from app.core.redis_client import get_cache_manager


class EmbeddingService:
    """
    Generates dense vector embeddings for RAG indexing and retrieval.
    
    Primary model: OpenAI text-embedding-3-large (1536 dimensions)
    Cache: Redis (TTL 24h) to avoid re-embedding identical text
    Batch size: 100 texts per API call
    """

    EMBEDDING_MODEL = settings.EMBEDDING_MODEL
    DIMENSIONS = settings.EMBEDDING_DIMENSIONS
    BATCH_SIZE = 100
    CACHE_TTL = 86400  # 24 hours

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=settings.openai.API_KEY)
        return self._client

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.
        Returns cached result if available.

        Args:
            text: Input text to embed (max ~8191 tokens)

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            return [0.0] * self.DIMENSIONS

        # Check cache first
        cache_key = f"embedding:{self._text_hash(text)}"
        try:
            cache = get_cache_manager()
            cached = await cache.get(cache_key)
            if cached:
                return cached
        except Exception:
            pass

        embedding = await self._generate_embedding(text)

        # Cache result
        try:
            await cache.set(cache_key, embedding, ttl=self.CACHE_TTL)
        except Exception:
            pass

        return embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts efficiently.
        Splits into API-sized batches and processes in parallel.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors in the same order as input
        """
        if not texts:
            return []

        # De-duplicate to avoid redundant API calls
        unique_texts = list(dict.fromkeys(texts))  # Preserve order, remove dupes
        text_to_embedding: dict[str, List[float]] = {}

        # Process in batches
        for i in range(0, len(unique_texts), self.BATCH_SIZE):
            batch = unique_texts[i : i + self.BATCH_SIZE]
            batch_embeddings = await self._generate_batch_embeddings(batch)
            for text, emb in zip(batch, batch_embeddings):
                text_to_embedding[text] = emb

        # Return in original order
        return [text_to_embedding.get(t, [0.0] * self.DIMENSIONS) for t in texts]

    async def embed_document(self, title: str, content: str) -> List[float]:
        """
        Embed a document with title prefix for better retrieval.
        Title is given extra weight by prepending.

        Args:
            title: Document title
            content: Document body text

        Returns:
            Combined embedding vector
        """
        # Prepend title for better semantic representation
        combined = f"Title: {title}\n\nContent: {content[:6000]}"
        return await self.embed_text(combined)

    async def _generate_embedding(self, text: str) -> List[float]:
        """Make a single embedding API call."""
        client = self._get_client()
        # Truncate to safe token limit (~6000 chars ≈ 1500 tokens)
        safe_text = text[:6000].strip()
        response = await client.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=safe_text,
            dimensions=self.DIMENSIONS,
        )
        return response.data[0].embedding

    async def _generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Make a batch embedding API call."""
        client = self._get_client()
        safe_texts = [t[:6000].strip() for t in texts]
        try:
            response = await client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=safe_texts,
                dimensions=self.DIMENSIONS,
            )
            # Sort by index to ensure order is preserved
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [d.embedding for d in sorted_data]
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            # Fall back to individual calls
            results = []
            for text in safe_texts:
                try:
                    emb = await self._generate_embedding(text)
                except Exception:
                    emb = [0.0] * self.DIMENSIONS
                results.append(emb)
            return results

    def _text_hash(self, text: str) -> str:
        """Generate a short hash for cache key."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    async def compute_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        Returns value between -1 and 1 (1 = identical).
        """
        import math
        dot = sum(a * b for a, b in zip(embedding1, embedding2))
        mag1 = math.sqrt(sum(a ** 2 for a in embedding1))
        mag2 = math.sqrt(sum(b ** 2 for b in embedding2))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)
