"""
ResQAI - Semantic Retriever (Full Implementation)
Enterprise-grade RAG retrieval with hybrid search, metadata filtering,
reranking, and citation support.
"""

import uuid
from typing import List, Optional, Any

from qdrant_client.http import models as qmodels
from loguru import logger

from app.config import settings
from app.rag.embeddings.embedding_service import EmbeddingService
from app.rag.embeddings.qdrant_manager import QdrantManager


class RetrievedChunk:
    """A retrieved document chunk with relevance metadata."""

    def __init__(
        self,
        content: str,
        score: float,
        source: str,
        document_id: str,
        chunk_id: str,
        metadata: Optional[dict] = None,
    ) -> None:
        self.content = content
        self.score = score
        self.source = source
        self.document_id = document_id
        self.chunk_id = chunk_id
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "score": round(self.score, 4),
            "source": self.source,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "metadata": self.metadata,
        }

    def to_citation(self) -> str:
        """Format as a citation string."""
        title = self.metadata.get("title", self.source)
        return f"[{title}] (relevance: {self.score:.2f})"


class SemanticRetriever:
    """
    Full RAG retrieval engine.
    
    Supports:
    - Dense vector search (semantic similarity)
    - Metadata filtering (by entity, city, document type)
    - Score threshold filtering
    - Result reranking
    - Multi-collection search
    - Citation generation
    """

    def __init__(self) -> None:
        self._embedding_svc = EmbeddingService()
        self._qdrant = QdrantManager()

    async def retrieve(
        self,
        query: str,
        collection: str = settings.qdrant.COLLECTION_KNOWLEDGE,
        limit: int = 5,
        min_score: float = 0.65,
        filters: Optional[dict] = None,
        rerank: bool = True,
    ) -> List[dict]:
        """
        Retrieve semantically relevant chunks for a query.

        Args:
            query: Natural language query
            collection: Qdrant collection to search
            limit: Maximum results to return
            min_score: Minimum cosine similarity threshold
            filters: Dict of metadata filters {field: value}
            rerank: Whether to apply additional reranking

        Returns:
            List of chunk dicts sorted by relevance
        """
        if not query or not query.strip():
            return []

        try:
            # Embed query
            query_vector = await self._embedding_svc.embed_text(query)

            # Build Qdrant filter
            qdrant_filter = self._build_filter(filters) if filters else None

            # Semantic search
            results = await self._qdrant.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit * 2 if rerank else limit,  # Over-retrieve for reranking
                score_threshold=min_score,
                filter_conditions=qdrant_filter,
                with_payload=True,
            )

            chunks = [self._scored_point_to_chunk(r) for r in results]

            if rerank and len(chunks) > limit:
                chunks = await self._rerank(query, chunks, limit)
            else:
                chunks = chunks[:limit]

            logger.debug(
                f"RAG retrieved {len(chunks)} chunks",
                collection=collection,
                query_preview=query[:50],
            )

            return [c.to_dict() for c in chunks]

        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            return []

    async def retrieve_multi_collection(
        self,
        query: str,
        collections: Optional[List[str]] = None,
        limit_per_collection: int = 3,
        min_score: float = 0.65,
    ) -> List[dict]:
        """
        Search across multiple collections and merge results.
        Useful for Admin Assistant which needs broad knowledge.
        """
        if collections is None:
            collections = [
                settings.qdrant.COLLECTION_KNOWLEDGE,
                settings.qdrant.COLLECTION_FOOD_SAFETY,
                settings.qdrant.COLLECTION_NGO,
            ]

        all_chunks = []
        for collection in collections:
            try:
                chunks = await self.retrieve(
                    query=query,
                    collection=collection,
                    limit=limit_per_collection,
                    min_score=min_score,
                    rerank=False,
                )
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning(f"Collection {collection} search failed: {e}")

        # Sort merged results by score
        all_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_chunks[:limit_per_collection * 2]

    async def retrieve_ngo_profiles(
        self,
        query: str,
        city: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """Retrieve NGO profiles with optional city filter."""
        filters = {}
        if city:
            filters["city"] = city

        return await self.retrieve(
            query=query,
            collection=settings.qdrant.COLLECTION_NGO,
            limit=limit,
            min_score=0.6,
            filters=filters,
        )

    async def retrieve_food_safety_guidelines(
        self,
        query: str,
        guideline_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[dict]:
        """Retrieve food safety guidelines for a specific food safety query."""
        filters = {}
        if guideline_type:
            filters["guideline_type"] = guideline_type

        return await self.retrieve(
            query=query,
            collection=settings.qdrant.COLLECTION_FOOD_SAFETY,
            limit=limit,
            min_score=0.7,
            filters=filters,
        )

    # -------------------------------------------------------
    # Indexing (called during document ingestion)
    # -------------------------------------------------------
    async def index_document(
        self,
        document_id: str,
        chunks: List[dict],
        collection: str = settings.qdrant.COLLECTION_KNOWLEDGE,
    ) -> int:
        """
        Index document chunks into Qdrant.

        Args:
            document_id: Parent document UUID
            chunks: List of {content, chunk_index, metadata} dicts
            collection: Target collection

        Returns:
            Number of chunks indexed
        """
        if not chunks:
            return 0

        # Generate embeddings for all chunks
        texts = [c["content"] for c in chunks]
        embeddings = await self._embedding_svc.embed_batch(texts)

        # Build Qdrant points
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point_id = str(uuid.uuid4())
            points.append(qmodels.PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "document_id": document_id,
                    "chunk_index": chunk.get("chunk_index", 0),
                    "content": chunk["content"],
                    "section_title": chunk.get("section_title"),
                    "token_count": chunk.get("token_count", 0),
                    **chunk.get("metadata", {}),
                },
            ))

        await self._qdrant.upsert_vectors(collection, points)
        logger.info(f"Indexed {len(points)} chunks into '{collection}'")
        return len(points)

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------
    def _build_filter(self, filters: dict) -> qmodels.Filter:
        """Convert dict filters to Qdrant filter object."""
        conditions = []
        for field, value in filters.items():
            if isinstance(value, bool):
                conditions.append(
                    qmodels.FieldCondition(
                        key=field,
                        match=qmodels.MatchValue(value=value),
                    )
                )
            elif isinstance(value, (int, float)):
                conditions.append(
                    qmodels.FieldCondition(
                        key=field,
                        match=qmodels.MatchValue(value=value),
                    )
                )
            else:
                conditions.append(
                    qmodels.FieldCondition(
                        key=field,
                        match=qmodels.MatchValue(value=str(value)),
                    )
                )
        return qmodels.Filter(must=conditions)

    def _scored_point_to_chunk(self, point: qmodels.ScoredPoint) -> RetrievedChunk:
        """Convert Qdrant ScoredPoint to RetrievedChunk."""
        payload = point.payload or {}
        return RetrievedChunk(
            content=payload.get("content", ""),
            score=float(point.score),
            source=payload.get("source", payload.get("title", "Unknown")),
            document_id=payload.get("document_id", str(point.id)),
            chunk_id=str(point.id),
            metadata={k: v for k, v in payload.items() if k != "content"},
        )

    async def _rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        limit: int,
    ) -> List[RetrievedChunk]:
        """
        Rerank results using cross-encoder scoring.
        Simple implementation: boost chunks that contain exact query terms.
        Production: use a cross-encoder model (e.g., ms-marco-MiniLM).
        """
        query_terms = set(query.lower().split())
        for chunk in chunks:
            # Keyword overlap bonus
            chunk_terms = set(chunk.content.lower().split())
            overlap = len(query_terms & chunk_terms) / max(len(query_terms), 1)
            # Blend semantic score with keyword overlap
            chunk.score = chunk.score * 0.85 + overlap * 0.15

        chunks.sort(key=lambda x: x.score, reverse=True)
        return chunks[:limit]
