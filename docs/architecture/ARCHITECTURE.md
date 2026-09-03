# ResQAI - System Architecture

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│   Browser (Next.js PWA)  │  Mobile (Responsive)  │  API Clients     │
└────────────────┬─────────────────────────────────────────────────────┘
                 │ HTTPS / WSS
┌────────────────▼─────────────────────────────────────────────────────┐
│                       NGINX (Reverse Proxy)                          │
│   Rate Limiting │ SSL Termination │ Load Balancing │ Static Assets   │
└────────────────┬─────────────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───▼──────────┐    ┌─────────▼──────────┐
│  Next.js     │    │   FastAPI Backend   │
│  Frontend    │    │   (ASGI / uvicorn)  │
│  Port 3000   │    │   Port 8000         │
└──────────────┘    └─────────┬──────────┘
                              │
            ┌─────────────────┼──────────────────┐
            │                 │                  │
    ┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
    │  REST API    │  │  GraphQL     │  │  WebSocket   │
    │  /api/v1     │  │  /graphql    │  │  /ws         │
    └──────────────┘  └──────────────┘  └──────────────┘
                              │
            ┌─────────────────┼──────────────────────────┐
            │                 │                          │
    ┌───────▼──────┐  ┌───────▼────────┐  ┌────────────▼──────┐
    │  AI          │  │   RAG Engine   │  │   MCP Protocol    │
    │ Orchestrator │  │   (Qdrant)     │  │   (15 Servers)    │
    └──────┬───────┘  └───────┬────────┘  └────────┬──────────┘
           │                  │                    │
    ┌──────▼───────────────────────────────────────▼──────────┐
    │                    10 AI Agents                          │
    │  FoodAnalysis │ NGOMatch │ RouteOpt │ Safety │ Demand    │
    │  Notification │ Volunteer │ Analytics │ Fraud │ Admin    │
    └──────────────────────────┬───────────────────────────────┘
                               │
    ┌──────────────────────────┼────────────────────────────────┐
    │                          │                                │
┌───▼──────┐  ┌────────────┐  ┌▼──────────┐  ┌──────────────┐ │
│PostgreSQL│  │   Redis    │  │  Qdrant   │  │    Kafka     │ │
│  (Main   │  │  (Cache +  │  │  (Vector  │  │  (Events +   │ │
│   DB)    │  │  PubSub)   │  │   Store)  │  │   Streaming) │ │
└──────────┘  └────────────┘  └───────────┘  └──────────────┘ │
                                                               │
    ┌──────────────────────────────────────────────────────────┘
    │
┌───▼──────────────────────────────────────────────────────────┐
│                    Celery Workers                            │
│    AI Tasks │ Notifications │ Reports │ Scheduled Jobs      │
└──────────────────────────────────────────────────────────────┘
```

## AI Model Assignment

| Task | Model | Rationale |
|------|-------|-----------|
| Food Image Analysis | Gemini 1.5 Pro Vision | Best multimodal vision model |
| NGO Matching | GPT-4o | Complex reasoning, profile comparison |
| Route Optimization | DeepSeek | Mathematical/algorithmic reasoning |
| Food Safety Check | Claude 3.5 Sonnet | Long-context document analysis (FSSAI) |
| Demand Prediction | GPT-4o | Statistical reasoning + historical data |
| Notification Content | Mistral Small | Lightweight text generation |
| Volunteer Assignment | Llama 3 (Ollama) | Offline-capable, privacy-preserving |
| Analytics Insights | GPT-4o | Complex multi-step analysis |
| Fraud Detection | DeepSeek | Pattern matching + code reasoning |
| Admin Chatbot | Claude 3.5 Sonnet | Conversational AI + long context |

## Clean Architecture Layers

```
┌──────────────────────────────────────────┐
│             API Layer (FastAPI)           │  ← Controllers / Routers
├──────────────────────────────────────────┤
│          Use Cases / Services            │  ← Business Logic
├──────────────────────────────────────────┤
│           Domain / Models                │  ← Entities, Value Objects
├──────────────────────────────────────────┤
│        Repository / Data Access          │  ← DB, Cache, External
└──────────────────────────────────────────┘
```

## Event-Driven Flow

```
Donation Created
    │
    ├──► Kafka Topic: resqai.donations
    │         │
    │    ┌────▼──────────────────┐
    │    │  AI Orchestrator      │
    │    │  Consumer Group       │
    │    └────┬──────────────────┘
    │         │
    │    ┌────▼──────────────────────────────┐
    │    │  Dispatches to:                   │
    │    │  1. Food Analysis Agent           │
    │    │  2. Food Safety Agent             │
    │    │  3. NGO Matching Agent            │
    │    │  4. Route Optimization Agent      │
    │    │  5. Volunteer Agent               │
    │    │  6. Notification Agent            │
    │    └────┬──────────────────────────────┘
    │         │
    │    ┌────▼──────────────────┐
    │    │  Kafka: ai-decisions  │
    │    └────┬──────────────────┘
    │         │
    │    ┌────▼──────────────────┐
    │    │  Analytics Consumer   │
    │    │  Updates KPIs + DB    │
    │    └───────────────────────┘
    │
    └──► WebSocket Push to Dashboard
```

## Security Architecture

```
Request → Nginx (TLS 1.3) → Rate Limit → CORS → JWT Validation → RBAC → Handler
                                                       │
                                              ┌────────▼──────────┐
                                              │  Permission Check  │
                                              │  per Role/Resource │
                                              └───────────────────┘
```
