# 🎬 CineAgent — Enterprise Agentic OTT Content Discovery Engine

> **Capstone Project — EAG (Engineering Agentic AI) V2 Course**
>
> A production-grade, multi-agent conversational system that helps users discover what to watch across OTT platforms through natural language — powered by System 2 reasoning, multi-provider LLM governance, episodic memory, and enterprise security.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Key AI Features](#key-ai-features)
- [Enterprise Features](#enterprise-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Evaluation Results](#evaluation-results)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Docker Deployment](#docker-deployment)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Design Decisions](#design-decisions)
- [Future Work](#future-work)

---

## Problem Statement

Traditional OTT recommendation engines rely on collaborative filtering and content-based approaches that:

- Don't understand **context** (mood, time available, who you're watching with)
- Can't **reason** about why a recommendation fits
- Don't work **across platforms** (Netflix, Prime, Hotstar, etc.)
- Offer no **explainability** — just "Because you watched X"
- Treat each session **independently** with no cross-session memory

Netflix users spend an average of **18 minutes browsing** before selecting content. CineAgent reduces this through conversational, intent-aware discovery.

---

## Solution

CineAgent is a **multi-agent system** built entirely from scratch (no LangChain) with enterprise-grade infrastructure:

- **System 2 Reasoning** (Draft-Verify-Refine) for self-critiqued, high-quality recommendations
- **Multi-Provider LLM Governance** — Anthropic Claude + Google Gemini with role-based model mapping
- **Automatic Provider Fallback** with exponential backoff — if Claude is down, retries then falls back to Gemini
- **Episodic Memory** with skeletonization to learn user preferences across conversations
- **Markdown Skills** for extensible OTT workflows (mood-based, group watch, binge planner)
- **Cross-platform catalog search** via TMDB API with real-time data enrichment
- **JWT Authentication** — Bearer token auth with configurable expiry
- **Rate Limiting** — Per-endpoint throttling (10/min for chat, 60/min for reads)
- **Prometheus Metrics** — Request counts, latency histograms, LLM call tracking
- **Input Sanitization** — Prompt injection detection and blocking
- **Structured Logging** — Trace IDs per request via `contextvars` for full observability
- **Token Counting & Cost Tracking** — Per request, per role, per provider with API endpoint
- **43 Automated Tests** — Unit + integration + enterprise feature tests, all passing
- **Automated Evaluation Benchmark** — 10+ queries, 91/100 avg quality, 100% success rate

---

## Key AI Features

### 1. Multi-Agent Orchestration
The Orchestrator routes each query through specialized agents — ProfilerAgent extracts intent, RecommendationAgent generates picks, TrendAnalyzerAgent handles trending content. No single monolithic prompt.

### 2. System 2 Reasoning (Draft-Verify-Refine)
Every recommendation goes through a verification loop. A separate Verifier LLM scores the draft 0–100. If below 85, an Optimizer refines it. Repeats up to 3 rounds — mimicking human "slow thinking."

### 3. Cross-Model Verification
The Verifier uses a **different LLM** than the Recommender (e.g., Claude verifies Gemini's output). This prevents self-confirmation bias — a genuinely independent quality check.

### 4. Role-Based Model Governance
Each AI role (profiler, recommender, verifier, optimizer) is mapped to a specific model/provider via YAML config. Swap any role between Claude Sonnet, Claude Haiku, Gemini Flash, or local Ollama without code changes.

### 5. Automatic Provider Fallback with Exponential Backoff
If the primary LLM provider fails, the system retries with exponential backoff (0.5s → 1s → 2s), then falls back to alternate providers. Fallback chain is built from the model registry — zero downtime.

### 6. Intent-Aware Profiling
ProfilerAgent extracts structured data from natural language: genres, mood, time constraints, group size, platform preferences — then passes this as structured context to downstream agents.

### 7. Episodic Memory with Skeletonization
Past conversations are compressed into lightweight "skeleton" traces (query → intent → recommendations → score) and stored in SQLite. These are injected into future prompts so the AI remembers prior sessions.

### 8. Preference Learning
The system extracts and persists user preferences (favorite genres, mood tendencies, preferred platforms) with confidence scores that update over multiple conversations.

### 9. Markdown Skill System
AI capabilities are defined as `.md` files (mood-based recommendation, group watch planner, binge planner). The SkillManager pattern-matches user queries to skills and injects the relevant skill instructions into the agent prompt at runtime.

### 10. Tool Use (Agentic Function Calling)
Agents call external tools — TMDB search, TMDB details enrichment, trending data — to ground recommendations in real data rather than hallucinating titles.

### 11. Reasoning Transparency
Every response includes a full trace: what the profiler extracted, which skill matched, each verification round's score and critique, which tools were called, and timing breakdown. Fully explainable AI.

### 12. Token Counting & Cost Tracking
Every LLM call tracks estimated input/output tokens and cost. Aggregated by provider, by role, and globally. Exposed via `/api/cost-tracker` and visible in the Analytics dashboard.

---

## Enterprise Features

| Feature | Implementation | Details |
|---------|---------------|---------|
| **JWT Authentication** | `PyJWT` + Bearer tokens | `/api/auth/token` issues tokens, all endpoints validate, 24h configurable expiry |
| **Rate Limiting** | `slowapi` per-IP | Chat: 10/min, all other endpoints: 60/min, configurable via env vars |
| **Input Sanitization** | Regex-based detection | Blocks prompt injection patterns (`ignore previous instructions`, `<\|im_start\|>`, etc.) |
| **Prometheus Metrics** | `prometheus-client` | `/metrics` endpoint: request counts, latency histograms, LLM calls, WS connections |
| **Structured Logging** | `contextvars` + custom formatter | Every log line includes `[trace_id]`, response headers include `X-Trace-ID` and `X-Response-Time-Ms` |
| **Rich Health Checks** | `/api/health` | Reports DB, LLM providers, TMDB, orchestrator, skills loaded, cost summary, uptime |
| **Exponential Backoff** | Built into `ModelManager` | Primary retries (0.5s, 1s, 2s) before falling back to alternate providers |
| **CORS Lockdown** | Whitelist-based | Only configured origins allowed (not `*`), explicit method/header restrictions |
| **Pydantic Validation** | `Field` constraints | Message length (1–2000), user_id (max 64), media_type enum, rating bounds (0–10) |
| **Global Error Handling** | HTTP middleware | Unhandled exceptions return structured JSON with trace_id, never raw 500s |
| **CI/CD Pipeline** | GitHub Actions | Backend tests, frontend build, Docker build — automated on push/PR |
| **Docker Compose** | Multi-container | Backend + Frontend + Nginx reverse proxy, one-command deployment |

---

## Architecture

```text
┌──────────────────────────────────────────────────────────────────┐
│                     React Frontend (Vite + TailwindCSS)          │
│   ┌──────┐ ┌────────┐ ┌─────────┐ ┌───────┐ ┌─────────┐       │
│   │ Chat │ │Trending│ │Watchlist│ │Profile│ │Analytics│       │
│   └──┬───┘ └───┬────┘ └────┬────┘ └───┬───┘ └────┬────┘       │
└──────┼─────────┼───────────┼──────────┼──────────┼──────────────┘
       │ REST/WS │           │ REST     │ REST     │ REST
┌──────▼─────────▼───────────▼──────────▼──────────▼──────────────┐
│  FastAPI Backend v2.0                                            │
│  ┌─────────────┬──────────────┬──────────────┬────────────────┐ │
│  │Rate Limiter │ JWT Auth     │ Trace ID MW  │ Prom. Metrics  │ │
│  │ (slowapi)   │ (PyJWT)      │ (contextvars)│ (/metrics)     │ │
│  └─────────────┴──────────────┴──────────────┴────────────────┘ │
│                          │                                       │
│               ┌──────────▼──────────┐                           │
│               │    Orchestrator     │                           │
│               │  Perception → Skill │                           │
│               │  Match → Action →   │                           │
│               │  Memory Save        │                           │
│               └──┬──────┬───────┬──┘                           │
│                  │      │       │                                │
│     ┌────────────▼┐ ┌───▼────┐ ┌▼──────────────┐              │
│     │  Profiler   │ │Recomm. │ │TrendAnalyzer  │              │
│     │  Agent      │ │ Agent  │ │   Agent       │              │
│     │(Claude      │ │(Claude │ │               │              │
│     │ Sonnet)     │ │ Sonnet)│ │               │              │
│     └─────────────┘ └───┬────┘ └───────────────┘              │
│                          │                                       │
│            ┌─────────────▼──────────────┐                       │
│            │   System 2 Reasoning       │                       │
│            │  Draft → Verify → Refine   │                       │
│            │  ┌─────────┐ ┌──────────┐  │                       │
│            │  │Verifier │ │Optimizer │  │                       │
│            │  │(Haiku)  │ │ (Haiku)  │  │                       │
│            │  └─────────┘ └──────────┘  │                       │
│            └─────────────┬──────────────┘                       │
│                          │                                       │
│     ┌────────────┬───────▼──────┬──────────────┐               │
│     │TMDB Search │  Streaming   │   Review     │               │
│     │  Tool      │ Availability │  Aggregator  │               │
│     └────────────┴──────────────┴──────────────┘               │
│                          │                                       │
│            ┌─────────────▼──────────────┐                       │
│            │   Episodic Memory (SQLite) │                       │
│            │  Episodes, Preferences,    │                       │
│            │  Watch History, Watchlist,  │                       │
│            │  Reasoning Logs            │                       │
│            └────────────────────────────┘                       │
│                          │                                       │
│     ┌────────────┬───────▼──────┬──────────────┐               │
│     │Cost Tracker│ Skill Manager│  Model Mgr   │               │
│     │(per-role)  │ (.md skills) │(multi-LLM +  │               │
│     │            │              │ fallback)     │               │
│     └────────────┴──────────────┴──────────────┘               │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Request** → Rate limiter → JWT auth → Trace ID assignment → Input sanitization
2. **Perception** — ProfilerAgent extracts intent, genres, mood, constraints
3. **Skill Matching** — SkillManager maps query to best Markdown skill (mood, group, binge)
4. **Memory Retrieval** — EpisodicMemory provides past preferences and session context
5. **Action** — RecommendationAgent drafts recommendations using TMDB tool data
6. **Verification** — System 2 Verifier (different LLM) scores quality 0–100
7. **Refinement** — If score < 85, Optimizer refines and re-verifies (up to 3 rounds)
8. **Response** — Enriched recommendations with posters, ratings, streaming info, reasoning trace, trace ID, and response time

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + Vite + TailwindCSS + Lucide Icons |
| **Backend** | Python FastAPI 0.115+ (lifespan, Pydantic V2) + WebSocket + Uvicorn |
| **LLM Providers** | Anthropic Claude (Sonnet 4, Haiku 3) + Google Gemini (2.5 Flash/Lite) |
| **Agentic Core** | Custom pipeline (no LangChain) — ModelManager, ReasoningEngine, EpisodicMemory, SkillManager |
| **Security** | JWT (PyJWT), Rate limiting (slowapi), CORS whitelist, Input sanitization |
| **Observability** | Prometheus metrics, Structured logging (contextvars trace IDs), Rich health checks |
| **Data** | TMDB API (real-time catalog, posters, ratings, streaming providers) |
| **Database** | SQLite (episodes, preferences, watch history, watchlist, reasoning logs) |
| **Testing** | Pytest + pytest-asyncio (43 tests: 17 API + 14 memory + 12 model manager) |
| **CI/CD** | GitHub Actions (backend tests → frontend build → Docker build) |
| **Containerization** | Docker + Docker Compose + Nginx reverse proxy |

---

## Evaluation Results

Automated benchmark suite with 10 diverse queries across 3 categories.

### Quality Metrics

| Metric | Value |
|--------|-------|
| **Success Rate** | 10/10 (100%) |
| **Average Quality Score** | 91/100 |
| **Median Score** | 90/100 |
| **Score Range** | 90 – 95 |
| **Above 85 Threshold** | 100% (10/10) |
| **Standard Deviation** | 2.1 |

### Latency

| Metric | Value |
|--------|-------|
| **Average** | 26.2s |
| **Median** | 26.2s |
| **P95** | 28.7s |
| **Range** | 24.8s – 28.7s |

### Category Breakdown

| Category | Success | Avg Score | Avg Latency |
|----------|---------|-----------|-------------|
| Simple Genre | 100% | 91/100 | 25.9s |
| Mood-Based | 100% | 91.7/100 | 26.4s |
| Constrained | 100% | 90/100 | 26.9s |

### Feature Coverage (all queries)

| Feature | Coverage |
|---------|----------|
| Reasoning Trace | 100% |
| Movie Posters | 100% |
| "Why" Explanations | 100% |
| Genre Tags | 100% |
| Tool Usage | 100% |
| Genre Match Accuracy | 100% |

### Test Suite

```
43 passed in 5.38s — 0 warnings
├── test_api.py          17 tests (health, CRUD, JWT, injection, metrics, tracing)
├── test_episodic_memory  14 tests (episodes, preferences, watchlist, history, reasoning)
└── test_model_manager    12 tests (config, roles, fallback, cost tracking, generation)
```

---

## Project Structure

```text
├── backend/
│   ├── agents/                    # Domain-specific agents
│   │   ├── orchestrator.py        # Central orchestrator (perception → action → memory)
│   │   ├── recommendation.py      # Content recommendation agent
│   │   ├── profiler.py            # User intent/preference profiler
│   │   └── trend_analyzer.py      # Trending content analyzer
│   ├── core/                      # Agentic pipeline modules
│   │   ├── model_manager.py       # Multi-provider LLM gateway + fallback + cost tracking
│   │   ├── reasoning.py           # System 2 Draft-Verify-Refine engine
│   │   ├── episodic_memory.py     # SQLite memory with skeletonization
│   │   ├── skill_manager.py       # Markdown skill loader + matcher
│   │   └── utils.py               # Structured logging with trace IDs
│   ├── tools/                     # Agent tools (function calling)
│   │   ├── tmdb_search.py         # TMDB movie/TV search + details
│   │   ├── streaming.py           # Streaming platform availability
│   │   └── review_aggregator.py   # Review/rating aggregation
│   ├── skills/                    # Markdown skills (hot-loadable)
│   │   ├── mood_based_rec/SKILL.md
│   │   ├── group_watch/SKILL.md
│   │   └── binge_planner/SKILL.md
│   ├── config/
│   │   └── models.yaml            # Model registry + role mappings + policies
│   ├── evaluation/                # Benchmark framework
│   │   ├── benchmark.py           # Automated evaluation suite
│   │   └── results/               # JSON benchmark reports
│   ├── tests/                     # 43 unit + integration tests
│   │   ├── test_api.py            # 17 API + enterprise feature tests
│   │   ├── test_episodic_memory.py# 14 memory CRUD tests
│   │   └── test_model_manager.py  # 12 model manager tests
│   ├── server.py                  # FastAPI v2.0 (JWT, rate limit, metrics, 18 endpoints)
│   ├── requirements.txt
│   └── .env                       # API keys (not committed)
├── frontend/
│   ├── src/
│   │   └── App.jsx                # 5-tab UI (Chat, Trending, Watchlist, Profile, Analytics)
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.js
├── .github/
│   └── workflows/ci.yml           # GitHub Actions CI pipeline
├── docker-compose.yml             # One-command deployment
├── Dockerfile.backend
├── Dockerfile.frontend
├── nginx.conf
└── README.md
```

---

## Setup & Installation

### Prerequisites

- Python 3.9+
- Node.js 18+
- API keys: [Google AI Studio](https://aistudio.google.com/apikey) (Gemini) and/or [Anthropic Console](https://console.anthropic.com) (Claude)
- TMDB API key: [TMDB Developer](https://developer.themoviedb.org)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your keys:
#   GEMINI_API_KEY=your_gemini_key
#   ANTHROPIC_API_KEY=your_anthropic_key
#   TMDB_API_KEY=your_tmdb_key

# Start server
python server.py
# → Running on http://localhost:8000
# → API docs at http://localhost:8000/api/docs
# → Health check at http://localhost:8000/api/health
# → Metrics at http://localhost:8000/metrics
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → Running on http://localhost:5173
```

### Run Tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
# → 43 passed in 5.38s
```

### Run Evaluation Benchmark

```bash
cd backend
source venv/bin/activate
python -m evaluation.benchmark --queries 10 --delay 5
# Outputs: quality scores, latency stats, category breakdown, feature coverage
# Results saved to: backend/evaluation/results/
```

---

## Docker Deployment

```bash
# One-command deployment
docker-compose up --build

# Frontend: http://localhost
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/api/docs
# Health: http://localhost:8000/api/health
# Metrics: http://localhost:8000/metrics
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/token` | Get JWT token (body: `{"user_id": "..."}`) |

All endpoints accept optional `Authorization: Bearer <token>` header.

### Core Endpoints

| Method | Endpoint | Rate Limit | Description |
|--------|----------|------------|-------------|
| `POST` | `/api/chat` | 10/min | Main chat — returns recommendations + full reasoning trace |
| `GET` | `/api/trending` | 60/min | Trending movies/shows from TMDB |
| `POST` | `/api/feedback` | 60/min | Submit feedback (liked/disliked/watched) |
| `GET` | `/api/preferences/{user_id}` | 60/min | Learned preferences with confidence scores |
| `POST` | `/api/watchlist` | 60/min | Add to watchlist |
| `DELETE` | `/api/watchlist/{user_id}/{tmdb_id}` | 60/min | Remove from watchlist |
| `GET` | `/api/watchlist/{user_id}` | 60/min | Get watchlist |
| `GET` | `/api/watch-history/{user_id}` | 60/min | Watch history with ratings |
| `GET` | `/api/episodes/{user_id}` | 60/min | Past session skeletons |
| `GET` | `/api/reasoning-stats/{user_id}` | 60/min | Reasoning analytics |
| `GET` | `/api/history/{user_id}` | 60/min | Conversation history |
| `DELETE` | `/api/conversation/{user_id}` | 60/min | Clear conversation |
| `GET` | `/api/skills` | 60/min | List loaded skills |
| `GET` | `/api/cost-tracker` | 60/min | Token usage + cost breakdown |

### Observability

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Rich health check (DB, LLM, TMDB, uptime, cost summary) |
| `GET` | `/metrics` | Prometheus-compatible metrics |
| `GET` | `/api/docs` | Interactive Swagger UI |
| `GET` | `/api/redoc` | ReDoc API documentation |
| `WS` | `/ws/{user_id}` | Real-time WebSocket chat |

### Response Headers

Every response includes:
- `X-Trace-ID` — Unique request trace identifier
- `X-Response-Time-Ms` — Server-side latency in milliseconds

---

## Testing

### Test Summary: 43 Tests, 0 Warnings

**API Integration Tests (17)**
- Health check, watchlist CRUD, reasoning stats, episodes, preferences, cost tracker, feedback, skills
- JWT token issuance, invalid token rejection (401)
- Prompt injection blocking (400)
- Rich health check validation (DB, orchestrator, providers, skills, usage)
- Prometheus metrics endpoint
- Trace ID presence in response headers
- Message length validation (Pydantic)

**Episodic Memory Unit Tests (14)**
- Episode save/retrieve, multiple episodes
- Preference CRUD with confidence updates
- Watch history tracking
- Watchlist add/remove
- Reasoning log persistence and aggregation
- Context formatting for prompts

**Model Manager Unit Tests (12)**
- Config loading from YAML
- Role resolution (profiler, recommender, verifier, optimizer)
- Fallback chain construction (excludes primary)
- Cost-per-1k token pricing
- Token estimation
- Cost tracker structure and increments
- Live generation tests (Claude + Gemini)

---

## Design Decisions

### Why No LangChain?
Building the agentic pipeline from scratch (ModelManager, ReasoningEngine, EpisodicMemory, SkillManager) demonstrates deep understanding of agentic patterns rather than framework dependency. Every component is ~100-200 lines of focused, readable code.

### Why Multi-Provider LLMs?
Using both Claude and Gemini demonstrates:
1. **Cross-model verification** — different models catch different failure modes
2. **Provider resilience** — automatic fallback with exponential backoff
3. **Cost optimization** — use cheaper models for lightweight tasks (formatting, verification)

### Why System 2 Reasoning?
Single-pass LLM responses frequently hallucinate movie titles or recommend irrelevant content. The Draft-Verify-Refine loop catches these errors before the user sees them. The verifier acts as an independent quality gate.

### Why Episodic Memory Skeletonization?
Storing full conversation transcripts is expensive and noisy. Skeletonization compresses sessions into structured traces (query → intent → recommendations → score), keeping only the information needed for preference learning.

### Why Markdown Skills?
Hardcoding recommendation strategies limits extensibility. Markdown skills can be added, modified, or A/B tested by non-engineers. The skill system is inspired by how human experts use mental frameworks for different scenarios.

### Why Enterprise Features?
JWT auth, rate limiting, input sanitization, Prometheus metrics, and structured logging are non-negotiable for any production AI system. These aren't just checkboxes — they protect against abuse, enable debugging, and provide operational visibility.

---

## Frontend Features

| Tab | Description |
|-----|-------------|
| **Chat** | Conversational AI with markdown rendering, quick prompts, expandable reasoning panels |
| **Trending** | Weekly/daily trending movies and shows from TMDB |
| **Watchlist** | Personal save-for-later list with add/remove (persisted in SQLite) |
| **Profile** | Learned preferences with confidence bars, watch history with feedback, past episodic sessions |
| **Analytics** | Reasoning dashboard: avg scores, rounds, latency, recent traces with score bars, system architecture cards |

---

## Future Work

- **PostgreSQL Migration** — Replace SQLite for production multi-user deployment
- **OAuth/SSO** — Social login (Google, GitHub) with proper credential verification
- **Streaming Availability API** — Real-time platform availability (JustWatch integration)
- **A/B Testing Framework** — Compare Claude vs Gemini recommendation quality side-by-side
- **Fine-Tuned Verifier** — Train a custom verification model on collected quality data
- **WebSocket Scaling** — Redis pub/sub for multi-instance WebSocket support
- **Content Gap Analysis** — Identify underserved user preferences for content acquisition insights

---

## Author

- **Gowtham** — EAG V2 Capstone Project

## License

MIT
