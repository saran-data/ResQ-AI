"""
ResQAI - GraphQL Schema
Strawberry GraphQL schema exposing donations, NGOs, restaurants, analytics.
"""

from typing import List, Optional
import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.scalars import JSON


@strawberry.type
class DonationGQL:
    id: str
    status: str
    total_servings: int
    total_weight_kg: float
    pickup_address: str
    created_at: str


@strawberry.type
class RestaurantGQL:
    id: str
    name: str
    city: str
    total_meals_saved: int
    sustainability_score: float


@strawberry.type
class NGOGraphQL:
    id: str
    name: str
    city: str
    capacity_per_day: int
    current_capacity: int


@strawberry.type
class KPIResponse:
    total_donations: int
    total_meals_saved: int
    carbon_saved_kg: float
    active_restaurants: int
    active_ngos: int


@strawberry.type
class Query:
    @strawberry.field(description="Get system KPIs")
    async def kpis(self) -> KPIResponse:
        # Full async DB access via info.context
        return KPIResponse(
            total_donations=0,
            total_meals_saved=0,
            carbon_saved_kg=0.0,
            active_restaurants=0,
            active_ngos=0,
        )

    @strawberry.field(description="Get recent donations")
    async def recent_donations(self, limit: int = 10) -> List[DonationGQL]:
        return []

    @strawberry.field(description="Get restaurant leaderboard")
    async def restaurant_leaderboard(self, limit: int = 10) -> List[RestaurantGQL]:
        return []


@strawberry.type
class Subscription:
    @strawberry.subscription(description="Real-time donation status updates")
    async def donation_status(self, donation_id: str):
        import asyncio
        # In production: subscribe to Redis pub/sub channel
        for i in range(3):
            yield f"status_update_{i}"
            await asyncio.sleep(1)


schema = strawberry.Schema(query=Query, subscription=Subscription)

graphql_router = GraphQLRouter(
    schema,
    graphiql=True,  # Enable GraphiQL playground
)
