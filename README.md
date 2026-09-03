# ResQAI - AI Powered Intelligent Food Rescue Ecosystem

> "Rescuing Surplus Food. Feeding Communities. Powered by AI."

---

## Overview

ResQAI is an enterprise-grade, multi-agent AI platform that autonomously rescues surplus food from restaurants, hotels, marriage halls, catering services, bakeries, and corporate cafeterias — and routes it to NGOs, orphanages, old age homes, shelters, and community kitchens.

The entire workflow is AI-driven. Humans only confirm actions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ResQAI Platform                          │
├─────────────────────────────────────────────────────────────────┤
│  Next.js Frontend  │  FastAPI Backend  │  AI Orchestrator       │
├─────────────────────────────────────────────────────────────────┤
│           Multi-Agent System (10 Specialized Agents)            │
│  Food Analysis | NGO Matching | Route | Safety | Prediction     │
│  Notification | Volunteer | Analytics | Fraud | Admin Bot       │
├─────────────────────────────────────────────────────────────────┤
│    RAG Engine (Qdrant)    │    MCP Protocol (15 Servers)        │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Redis  │  Qdrant  │  Cloudinary  │  Kafka       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Shadcn/UI |
| Backend | FastAPI (Python 3.11+) |
| Database | PostgreSQL 15, Redis 7, Qdrant |
| AI Models | GPT-4o, Claude 3.5, Gemini 1.5, Llama 3, DeepSeek, Mistral |
| Message Queue | Apache Kafka |
| Storage | Cloudinary |
| Auth | JWT + OAuth2 + RBAC |
| Infra | Docker, Docker Compose, Kubernetes-ready |
| Monitoring | Prometheus + Grafana |

---

## AI Agents

| Agent | Model | Responsibility |
|-------|-------|----------------|
| Food Analysis | Gemini 1.5 Vision | Image analysis, quantity estimation, freshness |
| NGO Matching | GPT-4o | Capacity, distance, preferences matching |
| Route Optimization | DeepSeek | A*, Dijkstra, VRP, TSP routing |
| Food Safety | Claude 3.5 | FSSAI guidelines, expiry, temperature checks |
| Demand Prediction | GPT-4o | Festival, weather, historical demand |
| Notification | Mistral | Multi-channel notifications |
| Volunteer | Llama 3 | Volunteer assignment optimization |
| Analytics | GPT-4o | KPIs, dashboards, carbon/meal savings |
| Fraud Detection | DeepSeek | Fake NGOs, suspicious patterns |
| Admin Assistant | Claude 3.5 | AI chatbot for system operations |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### 1. Clone & Setup

```bash
git clone https://github.com/your-org/resqai.git
cd resqai
cp .env.example .env
# Fill in your API keys in .env
```

### 2. Start with Docker Compose

```bash
docker-compose up -d
```

### 3. Run Migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Seed Database

```bash
docker-compose exec backend python scripts/seed.py
```

### 5. Access the Application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Grafana | http://localhost:3001 |
| Qdrant UI | http://localhost:6333/dashboard |
| Kafka UI | http://localhost:8080 |

---

## Environment Variables

See `.env.example` for all required environment variables.

Key sections:
- `DATABASE_*` — PostgreSQL connection
- `REDIS_*` — Redis connection
- `QDRANT_*` — Vector database
- `OPENAI_*` — OpenAI (GPT-4o)
- `ANTHROPIC_*` — Claude
- `GOOGLE_*` — Gemini + Maps
- `CLOUDINARY_*` — Image storage
- `TWILIO_*` — SMS + WhatsApp
- `SMTP_*` — Email
- `KAFKA_*` — Message queue

---

## Project Structure

```
resqai/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/v1/endpoints/  # REST API routes
│   │   ├── agents/            # 10 AI agents
│   │   ├── orchestrator/      # AI Orchestrator
│   │   ├── rag/               # RAG engine
│   │   ├── mcp/               # MCP servers & clients
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   ├── repositories/      # Data access layer
│   │   ├── core/              # Config, security, auth
│   │   ├── middleware/        # Custom middleware
│   │   ├── graphql/           # GraphQL schema
│   │   ├── websockets/        # Real-time connections
│   │   ├── tasks/             # Celery async tasks
│   │   └── events/            # Kafka event handlers
│   ├── alembic/               # Database migrations
│   └── tests/                 # Unit/Integration/E2E tests
├── frontend/                   # Next.js application
│   └── src/
│       ├── app/               # App router pages
│       ├── components/        # Reusable components
│       ├── lib/               # Utilities, stores, hooks
│       └── types/             # TypeScript types
├── infrastructure/             # DevOps
│   ├── docker/                # Dockerfiles
│   ├── kubernetes/            # K8s manifests
│   ├── monitoring/            # Prometheus + Grafana
│   └── terraform/             # IaC
├── database/                   # SQL schemas & seeds
├── docs/                       # Architecture docs
└── scripts/                    # Utility scripts
```

---

## Workflow

```
Restaurant uploads food
        ↓
Food Analysis Agent (Gemini) → quantity, freshness, classification
        ↓
Food Safety Agent (Claude) → FSSAI compliance check
        ↓
RAG Engine → retrieve NGO profiles, history, capacity
        ↓
NGO Matching Agent (GPT-4o) → rank & select best NGO
        ↓
Route Optimization Agent (DeepSeek) → optimal delivery route
        ↓
Volunteer Agent → assign nearest available volunteer
        ↓
Notification Agent → Email + SMS + WhatsApp alerts
        ↓
NGO accepts → OTP/QR verification
        ↓
Pickup → Real-time tracking
        ↓
Delivery → Confirmation
        ↓
Analytics Agent → update KPIs, carbon saved, meals saved
```

---

## API Documentation

- REST API: `http://localhost:8000/docs` (Swagger UI)
- ReDoc: `http://localhost:8000/redoc`
- GraphQL Playground: `http://localhost:8000/graphql`

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.
