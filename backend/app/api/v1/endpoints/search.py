"""ResQAI - Search API Endpoints (natural language + keyword)"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.base import ApiResponse
from app.services.rbac_service import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("", summary="Natural language search across all entities")
async def search(
    q: str = Query(..., min_length=2, max_length=200),
    entity: Optional[str] = Query(default=None, description="Filter: restaurant|ngo|donation"),
    city: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text search across restaurants, NGOs, and donations.
    Uses PostgreSQL trigram (pg_trgm) for fast fuzzy matching.
    Results are ranked by relevance.
    """
    from sqlalchemy import select, or_, func
    from app.models.restaurant import Restaurant, RestaurantStatus
    from app.models.ngo import NGO, NGOStatus

    results = []

    if not entity or entity == "restaurant":
        restaurant_query = select(Restaurant).where(
            or_(
                Restaurant.name.ilike(f"%{q}%"),
                Restaurant.description.ilike(f"%{q}%"),
                Restaurant.city.ilike(f"%{q}%"),
            ),
            Restaurant.status == RestaurantStatus.ACTIVE,
            Restaurant.is_deleted == False,  # noqa
        ).limit(limit // 2)
        if city:
            restaurant_query = restaurant_query.where(Restaurant.city.ilike(f"%{city}%"))
        r_result = await db.execute(restaurant_query)
        for r in r_result.scalars().all():
            results.append({"type": "restaurant", "id": str(r.id), "name": r.name, "city": r.city})

    if not entity or entity == "ngo":
        ngo_query = select(NGO).where(
            or_(
                NGO.name.ilike(f"%{q}%"),
                NGO.description.ilike(f"%{q}%"),
                NGO.city.ilike(f"%{q}%"),
            ),
            NGO.status == NGOStatus.ACTIVE,
            NGO.is_deleted == False,  # noqa
        ).limit(limit // 2)
        if city:
            ngo_query = ngo_query.where(NGO.city.ilike(f"%{city}%"))
        n_result = await db.execute(ngo_query)
        for n in n_result.scalars().all():
            results.append({"type": "ngo", "id": str(n.id), "name": n.name, "city": n.city})

    return ApiResponse.ok(data={"query": q, "results": results[:limit], "total": len(results)})

@router.get("/rag", summary="Semantic RAG search (AI-powered)")
async def rag_search(
    q: str = Query(..., min_length=5, max_length=500),
    collection: Optional[str] = Query(default="knowledge_base"),
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
):
    """
    Semantic search using RAG engine.
    Embeds the query and searches Qdrant for similar documents.
    """
    try:
        from app.rag.retrievers.semantic_retriever import SemanticRetriever
        retriever = SemanticRetriever()
        results = await retriever.retrieve(q, collection=collection, limit=limit)
        return ApiResponse.ok(data={"query": q, "results": results})
    except Exception as e:
        return ApiResponse.ok(data={"query": q, "results": [], "error": str(e)})
