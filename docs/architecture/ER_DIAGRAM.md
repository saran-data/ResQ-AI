# ResQAI - Entity Relationship Diagram

## Schema: `resqai`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ResQAI Database Schema                             │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐         ┌─────────────────────┐        ┌────────────────┐
│      USERS      │  1    1 │    RESTAURANTS       │  1   * │   DONATIONS    │
│─────────────────│─────────│─────────────────────│────────│────────────────│
│ PK id (UUID)    │         │ PK id (UUID)         │        │ PK id (UUID)   │
│ email (UNIQUE)  │         │ name                 │        │ FK restaurant_id│
│ phone           │         │ slug (UNIQUE)         │        │ FK matched_ngo_id│
│ name            │         │ type (enum)          │        │ FK volunteer_id │
│ role (enum)     │         │ fssai_license        │        │ status (enum)  │
│ status (enum)   │         │ latitude/longitude    │        │ total_servings │
│ hashed_password │         │ geohash               │        │ pickup_address │
│ oauth_provider  │         │ total_donations       │        │ pickup_lat/lng │
│ permissions     │         │ total_meals_saved     │        │ otp / qr_code  │
│ is_email_verified│         │ carbon_saved_kg       │        │ ai_safety_score│
│ created_at      │         │ sustainability_score  │        │ fraud_score    │
│ updated_at      │         │ FK owner_id           │        │ created_at     │
└─────────────────┘         └─────────────────────┘        └────────────────┘
        │ 1                          │ 1                             │ 1
        │                            │                               │
        │ 1                     ─────┘                               │ *
┌───────▼─────────┐                                       ┌──────────▼──────┐
│     NGOS         │                                       │   FOOD_ITEMS    │
│─────────────────│                                       │─────────────────│
│ PK id (UUID)    │                                       │ PK id (UUID)    │
│ name            │                                       │ FK donation_id  │
│ slug (UNIQUE)   │                                       │ name            │
│ type (enum)     │                                       │ category (enum) │
│ registration_no │                                       │ quantity/unit   │
│ beneficiaries   │                                       │ estimated_servings│
│ capacity_per_day│                                       │ is_vegetarian   │
│ food_preferences│                                       │ allergens[]     │
│ dietary_restrictions│                                   │ expiry_time     │
│ acceptance_rate │                                       │ image_urls[]    │
│ fraud_score     │                                       │ safety_status   │
│ latitude/longitude│                                     │ ai_analysis     │
│ FK manager_id   │                                       │ created_at      │
└─────────────────┘                                       └─────────────────┘

┌─────────────────┐         ┌─────────────────────┐
│   VOLUNTEERS    │  1    1 │      VEHICLES        │
│─────────────────│─────────│─────────────────────│
│ PK id (UUID)    │         │ PK id (UUID)         │
│ FK user_id      │         │ FK volunteer_id       │
│ badge_number    │         │ type (enum)           │
│ status (enum)   │         │ registration_number   │
│ is_available    │         │ capacity_kg           │
│ latitude/longitude│        │ has_refrigeration     │
│ geohash         │         │ insurance_number      │
│ service_radius_km│         └─────────────────────┘
│ rating          │
│ total_deliveries│
│ meals_delivered │
│ carbon_saved_kg │
└─────────────────┘
        │ 1
        │
        │ *
┌───────▼─────────┐         ┌─────────────────────┐
│   DELIVERIES    │  1    1 │       ROUTES         │
│─────────────────│─────────│─────────────────────│
│ PK id (UUID)    │         │ PK id (UUID)         │
│ FK donation_id  │         │ FK delivery_id        │
│ FK volunteer_id │         │ encoded_polyline      │
│ FK ngo_id       │         │ waypoints (JSONB)     │
│ status (enum)   │         │ total_distance_km     │
│ current_lat/lng │         │ total_duration_min    │
│ location_history│         │ algorithm (enum)      │
│ estimated_arrival│         │ traffic_data          │
│ actual_pickup_at│         │ weather_data          │
│ confirmed_by_ngo│         │ optimization_score    │
└─────────────────┘         └─────────────────────┘

┌─────────────────┐         ┌─────────────────────┐
│  NOTIFICATIONS  │         │    AI_DECISIONS      │
│─────────────────│         │─────────────────────│
│ PK id (UUID)    │         │ PK id (UUID)         │
│ FK user_id      │         │ FK donation_id        │
│ FK donation_id  │         │ agent_type (enum)     │
│ type (enum)     │         │ model_used            │
│ channel (enum)  │         │ input_data (JSONB)    │
│ title / message │         │ output_data (JSONB)   │
│ status (enum)   │         │ confidence_score      │
│ sent_at         │         │ reasoning             │
│ retry_count     │         │ explanation (XAI)     │
│ is_read         │         │ latency_ms            │
└─────────────────┘         │ cost_usd              │
                            │ citations (JSONB)     │
                            └─────────────────────┘

┌─────────────────────────┐  ┌─────────────────────┐
│    KNOWLEDGE_DOCUMENTS  │  │  ANALYTICS_SNAPSHOTS │
│─────────────────────────│  │─────────────────────│
│ PK id (UUID)            │  │ PK id (UUID)         │
│ title                   │  │ snapshot_date        │
│ document_type (enum)    │  │ snapshot_type (enum) │
│ source / source_url     │  │ total_donations      │
│ entity_type / entity_id │  │ total_meals_saved    │
│ total_chunks            │  │ carbon_saved_kg      │
│ qdrant_collection       │  │ avg_delivery_time    │
│ is_embedded             │  │ success_rate         │
│ tags[]                  │  │ by_city (JSONB)      │
│ is_active               │  │ top_restaurants      │
└────────────┬────────────┘  └─────────────────────┘
             │ 1
             │ *
┌────────────▼────────────┐  ┌─────────────────────┐
│    KNOWLEDGE_CHUNKS     │  │     AUDIT_LOGS        │
│─────────────────────────│  │─────────────────────│
│ PK id (UUID)            │  │ PK id (UUID)         │
│ FK document_id          │  │ FK user_id           │
│ content (TEXT)          │  │ http_method/path     │
│ chunk_index             │  │ resource_type        │
│ token_count             │  │ action               │
│ qdrant_point_id         │  │ old_values (JSONB)   │
│ qdrant_collection       │  │ new_values (JSONB)   │
│ retrieval_count         │  │ client_ip            │
└─────────────────────────┘  └─────────────────────┘
```

## Relationships Summary

| From | To | Type | Via |
|------|----|------|-----|
| User | Restaurant | 1:1 | owner_id |
| User | NGO | 1:1 | manager_id |
| User | Volunteer | 1:1 | user_id |
| Restaurant | Donation | 1:N | restaurant_id |
| NGO | Donation | 1:N | matched_ngo_id |
| Volunteer | Delivery | 1:N | volunteer_id |
| Volunteer | Vehicle | 1:1 | volunteer_id |
| Donation | FoodItem | 1:N | donation_id |
| Donation | Delivery | 1:1 | donation_id |
| Donation | AIDecision | 1:N | donation_id |
| Donation | Notification | 1:N | donation_id |
| Delivery | Route | 1:1 | delivery_id |
| KnowledgeDocument | KnowledgeChunk | 1:N | document_id |

## Qdrant Vector Collections

| Collection | Embeddings | Purpose |
|-----------|-----------|---------|
| `ngo_profiles` | NGO text summaries | NGO Matching Agent retrieval |
| `restaurant_profiles` | Restaurant summaries | Analytics, fraud detection |
| `food_safety_guidelines` | FSSAI/WHO guidelines | Food Safety Agent checks |
| `donation_history` | Historical donation records | Demand Prediction Agent |
| `knowledge_base` | General documents | Admin Assistant RAG |

## Key Design Decisions

1. **UUID primary keys** — portable, no sequence contention in distributed deployments
2. **Schema isolation** — all tables in `resqai` schema for multi-tenancy readiness  
3. **JSONB columns** — AI analysis, status history, operating hours stored as flexible JSON
4. **Geohash indexing** — fast proximity queries for NGO matching without PostGIS overhead
5. **Denormalized impact metrics** — total_donations, carbon_saved_kg on restaurants/volunteers for O(1) dashboard queries
6. **Soft deletes** — `is_deleted` flag preserves referential integrity and audit history
7. **No FK on knowledge_chunks.document_id** — avoids migration complexity; enforced at application level
