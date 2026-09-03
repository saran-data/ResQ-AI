"""
ResQAI - Knowledge Base Service
Manages the full document lifecycle: ingest → chunk → embed → index → retrieve.
Supports PDF, DOCX, plain text, and structured data sources.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.config import settings
from app.models.knowledge_base import KnowledgeDocument, KnowledgeChunk, DocumentType
from app.rag.chunkers.text_chunker import get_chunker_for_content_type
from app.rag.embeddings.embedding_service import EmbeddingService
from app.rag.retrievers.semantic_retriever import SemanticRetriever


# Map DocumentType to Qdrant collection
DOCUMENT_TYPE_COLLECTION: dict[DocumentType, str] = {
    DocumentType.NGO_PROFILE: settings.qdrant.COLLECTION_NGO,
    DocumentType.RESTAURANT_PROFILE: settings.qdrant.COLLECTION_RESTAURANT,
    DocumentType.FOOD_SAFETY_GUIDELINE: settings.qdrant.COLLECTION_FOOD_SAFETY,
    DocumentType.FSSAI_REGULATION: settings.qdrant.COLLECTION_FOOD_SAFETY,
    DocumentType.WHO_GUIDELINE: settings.qdrant.COLLECTION_FOOD_SAFETY,
    DocumentType.DONATION_HISTORY: settings.qdrant.COLLECTION_DONATIONS,
    DocumentType.GENERAL: settings.qdrant.COLLECTION_KNOWLEDGE,
    DocumentType.GOVERNMENT_NOTIFICATION: settings.qdrant.COLLECTION_KNOWLEDGE,
    DocumentType.VOLUNTEER_REPORT: settings.qdrant.COLLECTION_KNOWLEDGE,
    DocumentType.WEATHER_REPORT: settings.qdrant.COLLECTION_KNOWLEDGE,
    DocumentType.DEMAND_REPORT: settings.qdrant.COLLECTION_KNOWLEDGE,
}


class KnowledgeBaseService:
    """
    Manages the ResQAI knowledge base.
    Handles ingestion, chunking, embedding, and deletion of documents.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._embedding_svc = EmbeddingService()
        self._retriever = SemanticRetriever()

    async def ingest_text(
        self,
        title: str,
        content: str,
        document_type: DocumentType,
        source: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        tags: Optional[list] = None,
    ) -> KnowledgeDocument:
        """
        Ingest a plain text document into the knowledge base.

        Steps:
        1. Create KnowledgeDocument record
        2. Chunk the text
        3. Generate embeddings
        4. Index in Qdrant
        5. Save chunk records to PostgreSQL

        Args:
            title: Document title
            content: Document body text
            document_type: Classification
            source: Source name (FSSAI, WHO, etc.)
            entity_type: Related entity type (ngo, restaurant)
            entity_id: Related entity UUID
            metadata: Extra key-value metadata
            tags: Searchable tags

        Returns:
            Created KnowledgeDocument instance
        """
        doc = KnowledgeDocument(
            title=title,
            document_type=document_type,
            source=source,
            raw_content=content,
            processed_content=content,
            entity_type=entity_type,
            entity_id=uuid.UUID(entity_id) if entity_id else None,
            metadata=metadata or {},
            tags=tags or [],
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimensions=settings.EMBEDDING_DIMENSIONS,
            qdrant_collection=DOCUMENT_TYPE_COLLECTION.get(
                document_type, settings.qdrant.COLLECTION_KNOWLEDGE
            ),
            is_active=True,
        )
        self._db.add(doc)
        await self._db.flush()

        # Chunk the document
        chunker = get_chunker_for_content_type(document_type.value)
        raw_chunks = chunker.chunk(
            content,
            metadata={
                "title": title,
                "source": source or "",
                "document_type": document_type.value,
                "entity_type": entity_type or "",
                "entity_id": entity_id or "",
                **(metadata or {}),
            },
        )

        if not raw_chunks:
            logger.warning(f"Document '{title}' produced no chunks")
            return doc

        # Index chunks into Qdrant
        chunk_dicts = [
            {
                "content": c.content,
                "chunk_index": c.chunk_index,
                "section_title": c.section_title,
                "token_count": c.token_count,
                "metadata": c.metadata or {},
            }
            for c in raw_chunks
        ]

        collection = doc.qdrant_collection
        indexed_count = await self._retriever.index_document(
            document_id=str(doc.id),
            chunks=chunk_dicts,
            collection=collection,
        )

        # Save chunk records to PostgreSQL
        for i, raw_chunk in enumerate(raw_chunks):
            chunk = KnowledgeChunk(
                document_id=doc.id,
                content=raw_chunk.content,
                chunk_index=raw_chunk.chunk_index,
                token_count=raw_chunk.token_count,
                char_count=len(raw_chunk.content),
                section_title=raw_chunk.section_title,
                start_char=raw_chunk.char_start,
                end_char=raw_chunk.char_end,
                qdrant_collection=collection,
                embedding_model=settings.EMBEDDING_MODEL,
                is_active=True,
            )
            self._db.add(chunk)

        # Update document status
        from sqlalchemy import update
        await self._db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == doc.id)
            .values(
                total_chunks=len(raw_chunks),
                is_embedded=True,
                last_embedded_at=datetime.now(timezone.utc).isoformat(),
            )
        )

        logger.info(
            f"Document ingested",
            title=title,
            chunks=len(raw_chunks),
            collection=collection,
            doc_id=str(doc.id),
        )
        return doc

    async def ingest_ngo_profile(self, ngo) -> KnowledgeDocument:
        """
        Create a RAG-indexed profile for an NGO.
        Called after NGO verification to keep knowledge base current.
        """
        content = f"""NGO Profile: {ngo.name}

Type: {ngo.type.value if ngo.type else 'NGO'}
City: {ngo.city}, {ngo.state}
Registration: {ngo.registration_number or 'Not provided'}
DARPAN ID: {ngo.darpan_id or 'Not provided'}

About: {ngo.description or 'No description available'}
Mission: {ngo.mission_statement or 'Not specified'}

Capacity:
- Daily capacity: {ngo.capacity_per_day} servings
- Current capacity: {ngo.current_capacity} servings
- Beneficiaries: {ngo.beneficiaries_count} people
- Storage available: {'Yes' if ngo.storage_available else 'No'}
- Refrigeration: {'Yes' if ngo.refrigeration_available else 'No'}

Food Preferences: {', '.join(ngo.food_preferences or ['All types'])}
Dietary Restrictions: {', '.join(ngo.dietary_restrictions or ['None'])}
Service Hours: {str(ngo.service_hours or 'Contact for details')}

Performance:
- Acceptance rate: {ngo.acceptance_rate * 100:.1f}%
- Average response time: {ngo.avg_response_time_minutes:.0f} minutes
- Total donations received: {ngo.total_received}
- Meals distributed: {ngo.total_meals_distributed:,}
"""
        return await self.ingest_text(
            title=f"NGO Profile: {ngo.name}",
            content=content,
            document_type=DocumentType.NGO_PROFILE,
            source="resqai_platform",
            entity_type="ngo",
            entity_id=str(ngo.id),
            metadata={"city": ngo.city, "type": ngo.type.value if ngo.type else "ngo", "is_verified": ngo.is_verified},
            tags=["ngo", ngo.city, ngo.type.value if ngo.type else "ngo"],
        )

    async def ingest_fssai_guidelines(self) -> list:
        """Load core FSSAI food safety guidelines into the knowledge base."""
        guidelines = [
            {
                "title": "FSSAI Temperature Control Guidelines",
                "content": """FSSAI Food Safety Guidelines: Temperature Control

Cold chain requirements:
- Dairy products: 0-4°C
- Cooked foods: Must be served above 60°C or stored below 5°C
- Frozen foods: -18°C or below
- Fresh meat/fish: 0-4°C

Temperature Danger Zone: 5°C to 60°C
Foods left in the danger zone for more than 2 hours are considered unsafe.
Cooked food left at room temperature (25-30°C) is safe for maximum 2 hours.

Reheating requirements:
- Reheat to minimum 74°C internal temperature
- Do not reheat more than once

For food rescue operations:
- Cooked meals must be consumed within 4 hours of preparation
- Maintain temperature logs for all temperature-sensitive items
- Refrigerated food must reach the recipient within 6 hours of pickup""",
                "tags": ["temperature", "cold_chain", "fssai", "safety"],
            },
            {
                "title": "FSSAI Food Labeling Requirements for Donations",
                "content": """FSSAI Labeling Requirements for Donated Food

All donated food packages must carry:
1. Name of food item
2. Date and time of preparation
3. Ingredients/allergens list
4. Storage instructions
5. Vegetarian/Non-vegetarian symbol (Green dot = Veg, Red dot = Non-veg)
6. Name of donating establishment
7. FSSAI license number of donor

Allergens requiring mandatory declaration:
- Gluten (wheat, barley, rye)
- Dairy/milk products
- Eggs
- Fish and shellfish
- Tree nuts (almonds, cashews, walnuts, etc.)
- Peanuts
- Soybeans
- Sesame seeds

Religious dietary considerations:
- Clearly mark Halal and Jain food items
- Separate handling for vegetarian items""",
                "tags": ["labeling", "allergens", "fssai", "compliance"],
            },
        ]

        docs = []
        for guideline in guidelines:
            doc = await self.ingest_text(
                title=guideline["title"],
                content=guideline["content"],
                document_type=DocumentType.FSSAI_REGULATION,
                source="FSSAI",
                metadata={"authority": "FSSAI", "country": "India"},
                tags=guideline.get("tags", []),
            )
            docs.append(doc)

        logger.info(f"Ingested {len(docs)} FSSAI guidelines")
        return docs

    async def delete_document(self, document_id: str) -> bool:
        """Remove a document and its vectors from both PostgreSQL and Qdrant."""
        from sqlalchemy import select, update
        from app.rag.embeddings.qdrant_manager import QdrantManager

        result = await self._db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return False

        # Get chunk IDs for Qdrant deletion
        chunk_result = await self._db.execute(
            select(KnowledgeChunk.qdrant_point_id)
            .where(KnowledgeChunk.document_id == document_id, KnowledgeChunk.qdrant_point_id.isnot(None))
        )
        qdrant_ids = [row[0] for row in chunk_result.all()]

        if qdrant_ids and doc.qdrant_collection:
            try:
                qdrant = QdrantManager()
                await qdrant.delete_vectors(doc.qdrant_collection, qdrant_ids)
            except Exception as e:
                logger.warning(f"Qdrant deletion failed: {e}")

        # Soft-delete in PostgreSQL
        await self._db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(is_active=False)
        )
        await self._db.execute(
            update(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .values(is_active=False)
        )
        return True
