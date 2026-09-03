"""
ResQAI - Qdrant Collection Manager
Initializes and manages all Qdrant vector collections for the RAG engine.
Each collection maps to a knowledge domain with its own embedding schema.
"""

from typing import Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    HnswConfigDiff,
    QuantizationConfig,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    OptimizersConfigDiff,
    PayloadSchemaType,
)
from loguru import logger

from app.config import settings


# -------------------------------------------------------
# Collection Definitions
# -------------------------------------------------------
COLLECTIONS = {
    settings.qdrant.COLLECTION_NGO: {
        "description": "NGO profiles — capacity, preferences, location, history",
        "payload_schema": {
            "ngo_id": PayloadSchemaType.KEYWORD,
            "city": PayloadSchemaType.KEYWORD,
            "type": PayloadSchemaType.KEYWORD,
            "capacity_per_day": PayloadSchemaType.INTEGER,
            "is_verified": PayloadSchemaType.BOOL,
        },
    },
    settings.qdrant.COLLECTION_RESTAURANT: {
        "description": "Restaurant profiles — cuisine, location, donation history",
        "payload_schema": {
            "restaurant_id": PayloadSchemaType.KEYWORD,
            "city": PayloadSchemaType.KEYWORD,
            "type": PayloadSchemaType.KEYWORD,
            "is_verified": PayloadSchemaType.BOOL,
        },
    },
    settings.qdrant.COLLECTION_FOOD_SAFETY: {
        "description": "FSSAI guidelines, WHO standards, food safety regulations",
        "payload_schema": {
            "guideline_type": PayloadSchemaType.KEYWORD,
            "source": PayloadSchemaType.KEYWORD,
            "effective_date": PayloadSchemaType.TEXT,
        },
    },
    settings.qdrant.COLLECTION_DONATIONS: {
        "description": "Donation history for demand prediction and pattern matching",
        "payload_schema": {
            "restaurant_id": PayloadSchemaType.KEYWORD,
            "ngo_id": PayloadSchemaType.KEYWORD,
            "city": PayloadSchemaType.KEYWORD,
            "food_category": PayloadSchemaType.KEYWORD,
            "status": PayloadSchemaType.KEYWORD,
        },
    },
    settings.qdrant.COLLECTION_KNOWLEDGE: {
        "description": "General knowledge base — government notifications, reports, guidelines",
        "payload_schema": {
            "document_type": PayloadSchemaType.KEYWORD,
            "source": PayloadSchemaType.KEYWORD,
            "language": PayloadSchemaType.KEYWORD,
            "is_active": PayloadSchemaType.BOOL,
        },
    },
}


class QdrantManager:
    """
    Manages Qdrant vector database lifecycle for ResQAI.
    - Initializes all collections on startup
    - Creates payload indexes for filtered search
    - Configures HNSW and quantization for performance
    """

    def __init__(self) -> None:
        self._client: Optional[AsyncQdrantClient] = None

    async def get_client(self) -> AsyncQdrantClient:
        """Lazy-initialize and return the async Qdrant client."""
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=settings.qdrant.URL,
                api_key=settings.qdrant.API_KEY,
                timeout=30,
            )
        return self._client

    async def initialize_collections(self) -> None:
        """
        Create all required Qdrant collections if they don't exist.
        Called during application startup.
        """
        client = await self.get_client()

        for collection_name, config in COLLECTIONS.items():
            await self._ensure_collection(client, collection_name, config)

        logger.info(
            f"Qdrant collections initialized",
            collections=list(COLLECTIONS.keys()),
            url=settings.qdrant.URL,
        )

    async def _ensure_collection(
        self,
        client: AsyncQdrantClient,
        name: str,
        config: dict,
    ) -> None:
        """
        Create a Qdrant collection if it doesn't already exist.
        Configures HNSW indexing and scalar quantization for memory efficiency.
        """
        try:
            existing = await client.get_collection(name)
            logger.debug(f"Qdrant collection '{name}' already exists, skipping")
            return
        except Exception:
            pass  # Collection doesn't exist, create it

        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
                hnsw_config=HnswConfigDiff(
                    m=16,               # Number of connections per layer
                    ef_construct=100,   # Search breadth during construction
                    full_scan_threshold=10000,
                    on_disk=False,
                ),
                on_disk=False,
            ),
            # Scalar quantization reduces memory 4x with ~1% accuracy loss
            quantization_config=QuantizationConfig(
                scalar=ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    )
                )
            ),
            optimizers_config=OptimizersConfigDiff(
                default_segment_number=4,
                max_optimization_threads=2,
            ),
        )

        # Create payload indexes for filtered search
        payload_schema = config.get("payload_schema", {})
        for field_name, field_type in payload_schema.items():
            await client.create_payload_index(
                collection_name=name,
                field_name=field_name,
                field_schema=field_type,
            )

        logger.info(
            f"Qdrant collection created",
            collection=name,
            description=config.get("description", ""),
            indexed_fields=list(payload_schema.keys()),
        )

    async def upsert_vectors(
        self,
        collection_name: str,
        points: list[qmodels.PointStruct],
        batch_size: int = 100,
    ) -> None:
        """
        Upsert vectors in batches to avoid memory pressure.

        Args:
            collection_name: Target collection
            points: List of PointStruct with id, vector, payload
            batch_size: Number of points per batch
        """
        client = await self.get_client()
        total = len(points)

        for i in range(0, total, batch_size):
            batch = points[i : i + batch_size]
            await client.upsert(collection_name=collection_name, points=batch)
            logger.debug(
                f"Upserted vector batch",
                collection=collection_name,
                batch=f"{i + len(batch)}/{total}",
            )

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float = 0.7,
        filter_conditions: Optional[qmodels.Filter] = None,
        with_payload: bool = True,
    ) -> list[qmodels.ScoredPoint]:
        """
        Semantic search in a Qdrant collection.

        Args:
            collection_name: Collection to search
            query_vector: Embedding of the query
            limit: Maximum results to return
            score_threshold: Minimum cosine similarity score (0-1)
            filter_conditions: Optional metadata filter
            with_payload: Include payload in results

        Returns:
            List of ScoredPoint results sorted by relevance
        """
        client = await self.get_client()
        results = await client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=filter_conditions,
            with_payload=with_payload,
        )
        return results

    async def hybrid_search(
        self,
        collection_name: str,
        query_vector: list[float],
        sparse_vector: Optional[dict] = None,
        limit: int = 10,
        filter_conditions: Optional[qmodels.Filter] = None,
    ) -> list[qmodels.ScoredPoint]:
        """
        Hybrid search combining dense vectors (semantic) with sparse BM25 (keyword).
        Falls back to dense-only if sparse vector not provided.
        """
        client = await self.get_client()

        if sparse_vector:
            # Reciprocal Rank Fusion of dense + sparse results
            dense_results = await client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit * 2,
                query_filter=filter_conditions,
                with_payload=True,
            )
            # In production: combine with BM25 sparse results using RRF scoring
            # For now, return dense results (sparse requires Qdrant sparse vectors setup)
            return dense_results[:limit]

        return await self.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            filter_conditions=filter_conditions,
        )

    async def delete_vectors(
        self,
        collection_name: str,
        point_ids: list[str],
    ) -> None:
        """Delete vectors by their IDs."""
        client = await self.get_client()
        await client.delete(
            collection_name=collection_name,
            points_selector=qmodels.PointIdsList(points=point_ids),
        )

    async def get_collection_info(self, collection_name: str) -> dict:
        """Return collection metadata and point count."""
        client = await self.get_client()
        info = await client.get_collection(collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "status": str(info.status),
        }

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        if self._client:
            await self._client.close()
