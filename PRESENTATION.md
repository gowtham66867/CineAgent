# CineAgent — Enterprise Agentic OTT Content Discovery Engine

## Capstone Project | EAG V2 — Engineering Agentic AI

**Author:** Gowtham

---

## Slide 1: The Problem

### Users Waste 18 Minutes Browsing Netflix Before Picking Something

- Traditional recommendations use **collaborative filtering** — no understanding of context
- No awareness of **mood**, **time available**, or **who you're watching with**
- Recommendations are **siloed per platform** — Netflix doesn't know what you watched on Prime
- Zero **explainability** — just "Because you watched X"
- Every session starts from **scratch** — no cross-session memory

**Goal:** Build an AI that *talks* to you, *remembers* you, and *explains* why it recommends what it does.

---

## Slide 2: The Solution — CineAgent

### A Multi-Agent System Built From Scratch (No LangChain)

```
User: "I'm feeling sad, cheer me up with something light"

→ ProfilerAgent extracts: mood=sad, intent=comfort, genre=comedy/feel-good
→ SkillManager matches: mood-based-recommendation skill
→ RecommendationAgent drafts 5 picks using TMDB real data
→ Verifier LLM (different model) scores: 95/100 ✓
→ Response: 5 movies with posters, ratings, streaming info, and "why" explanations
```

**Key Differentiators:**
- System 2 Reasoning (Draft → Verify → Refine)
- Cross-model verification (Claude verifies Gemini's output)
- Episodic memory that learns preferences across sessions
- Enterprise-grade security and observability

---

## Slide 3: Architecture Overview

```
┌─────────── Frontend (React + Vite + TailwindCSS) ───────────┐
│   Chat │ Trending │ Watchlist │ Profile │ Analytics          │
└──────────────────────┬───────────────────────────────────────┘
                       │ REST / WebSocket
┌──────────────────────▼───────────────────────────────────────┐
│  FastAPI Backend v2.0                                         │
│  ┌──────────┬──────────┬──────────────┬────────────────┐     │
│  │Rate Limit│ JWT Auth │ Trace ID MW  │ Prom. Metrics  │     │
│  └──────────┴──────────┴──────────────┴────────────────┘     │
│                       │                                       │
│            ┌──────────▼──────────┐                            │
│            │    Orchestrator     │                            │
│            │  Perception → Skill │                            │
│            │  Match → Action →   │                            │
│            │  Memory Save        │                            │
│            └──┬──────┬───────┬──┘                            │
│               │      │       │                                │
│     ┌─────────▼┐ ┌───▼───┐ ┌▼──────────┐                    │
│     │ Profiler │ │Recomm.│ │  Trend    │                    │
│     │ Agent    │ │ Agent │ │ Analyzer  │                    │
│     └──────────┘ └───┬───┘ └───────────┘                    │
│                      │                                        │
│         ┌────────────▼────────────┐                           │
│         │  System 2 Reasoning     │                           │
│         │  Draft → Verify → Refine│                           │
│         │  (Verifier = Haiku)     │                           │
│         │  (Recommender = Sonnet) │                           │
│         └────────────┬────────────┘                           │
│                      │                                        │
│    ┌─────────┬───────▼─────┬──────────┐                      │
│    │  TMDB   │  Streaming  │  Review  │                      │
│    │  Tool   │  Avail.     │  Aggr.   │                      │
│    └─────────┴─────────────┴──────────┘                      │
│                      │                                        │
│         ┌────────────▼────────────┐                           │
│         │  Episodic Memory        │                           │
│         │  (SQLite + Skeletons)   │                           │
│         └─────────────────────────┘                           │
└───────────────────────────────────────────────────────────────┘
```

---

## Slide 4: 12 Key AI Features

| # | Feature | How It Works |
|---|---------|-------------|
| 1 | **Multi-Agent Orchestration** | Orchestrator routes to ProfilerAgent, RecommendationAgent, TrendAnalyzer |
| 2 | **System 2 Reasoning** | Draft-Verify-Refine loop. Verifier scores 0–100, rejects below 85 |
| 3 | **Cross-Model Verification** | Verifier (Claude Haiku) independently checks Recommender (Claude Sonnet) |
| 4 | **Role-Based Model Governance** | YAML config maps roles → models. Swap Claude/Gemini/Ollama per role |
| 5 | **Provider Fallback + Backoff** | Exponential retry (0.5s→1s→2s), then alternate provider chain |
| 6 | **Intent-Aware Profiling** | Extracts genres, mood, constraints, platforms from natural language |
| 7 | **Episodic Memory** | Past sessions compressed to skeletons, injected into future prompts |
| 8 | **Preference Learning** | Confidence-scored preferences updated across conversations |
| 9 | **Markdown Skills** | `.md` files define strategies (mood, group watch, binge). Hot-loadable |
| 10 | **Tool Use** | TMDB search, details, trending — grounds recs in real data |
| 11 | **Reasoning Transparency** | Full trace: profiler output, skill match, scores, tool calls, timing |
| 12 | **Cost Tracking** | Token counting per request/role/provider. API + dashboard |

---

## Slide 5: Enterprise Features

| Feature | Technology | Why It Matters |
|---------|-----------|---------------|
| **JWT Authentication** | PyJWT + Bearer tokens | Per-user isolation, 24h configurable expiry |
| **Rate Limiting** | slowapi | Chat: 10/min, reads: 60/min — prevents abuse |
| **Prompt Injection Guard** | Regex detection | Blocks `ignore previous instructions` and similar attacks |
| **Prometheus Metrics** | prometheus-client | `/metrics` — request counts, latency histograms, LLM calls |
| **Structured Logging** | contextvars | Every log line tagged with `[trace_id]`, headers: `X-Trace-ID` |
| **Rich Health Checks** | `/api/health` | DB status, LLM providers, TMDB, skills, uptime, cost summary |
| **Exponential Backoff** | ModelManager | Retries before fallback — handles transient LLM failures |
| **CORS Lockdown** | Whitelist | Only configured origins, explicit methods/headers |
| **Pydantic V2 Validation** | Field constraints | Length limits, enums, bounds — rejects bad input at the edge |
| **Global Error Handling** | HTTP middleware | Structured JSON errors with trace_id, never raw 500s |
| **CI/CD** | GitHub Actions | Backend tests → frontend build → Docker build on every push |
| **Docker Compose** | Multi-container | Backend + Frontend + Nginx, one-command deployment |

---

## Slide 6: Evaluation Results

### Automated Benchmark: 10 Queries Across 3 Categories

| Metric | Result |
|--------|--------|
| **Success Rate** | 10/10 (100%) |
| **Average Quality Score** | 91/100 |
| **Score Range** | 90 – 95 |
| **All Above 85 Threshold** | 100% |
| **Average Latency** | 26.2s |
| **P95 Latency** | 28.7s |

### Per-Category Performance

| Category | Success | Avg Score | Avg Latency |
|----------|---------|-----------|-------------|
| Simple Genre (e.g., "sci-fi movies") | 100% | 91 | 25.9s |
| Mood-Based (e.g., "feeling sad, cheer me up") | 100% | 91.7 | 26.4s |
| Constrained (e.g., "short movie under 90 min") | 100% | 90 | 26.9s |

### Feature Coverage: 100% Across All Queries

- Reasoning traces, movie posters, "why" explanations, genre tags, tool usage, genre match accuracy

---

## Slide 7: Test Suite

### 43 Tests | 0 Warnings | 5.38 seconds

```
tests/test_api.py             17 passed
tests/test_episodic_memory.py 14 passed
tests/test_model_manager.py   12 passed
────────────────────────────────────────
TOTAL                          43 passed
```

**API Tests (17):** Health, CRUD, JWT auth, injection blocking, Prometheus, tracing, validation

**Memory Tests (14):** Episodes, preferences, watchlist, watch history, reasoning logs, context formatting

**Model Manager Tests (12):** Config, roles, fallback chains, cost tracking, live LLM generation

---

## Slide 8: Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, TailwindCSS, Lucide Icons |
| **Backend** | Python FastAPI 0.115+, Pydantic V2, Uvicorn, WebSocket |
| **LLM Providers** | Claude Sonnet 4, Claude Haiku 3, Gemini 2.5 Flash |
| **Agentic Core** | Custom (no LangChain) — ModelManager, ReasoningEngine, EpisodicMemory, SkillManager |
| **Security** | JWT, Rate limiting, CORS whitelist, Input sanitization |
| **Observability** | Prometheus, Structured logging, Rich health checks |
| **Data** | TMDB API, SQLite |
| **DevOps** | Docker Compose, GitHub Actions CI, Nginx |

---

## Slide 9: Design Decisions

### Why No LangChain?

Building ModelManager, ReasoningEngine, EpisodicMemory, SkillManager from scratch (~100-200 lines each) demonstrates **deep understanding** of agentic patterns rather than framework dependency.

### Why Multi-Provider LLMs?

1. **Cross-model verification** — different models catch different failure modes
2. **Provider resilience** — auto fallback with exponential backoff
3. **Cost optimization** — cheap models (Haiku) for verification, powerful models (Sonnet) for generation

### Why System 2 Reasoning?

Single-pass LLM responses hallucinate movie titles and recommend irrelevant content. The Draft-Verify-Refine loop acts as an **independent quality gate** — catching 100% of issues before the user sees them.

### Why Episodic Memory Skeletonization?

Full transcripts are expensive and noisy. Skeletons compress sessions to `query → intent → recs → score`, keeping only what's needed for preference learning.

---

## Slide 10: Live Demo Flow

### Try These Queries:

1. **"Suggest a sci-fi movie"** → Genre detection, TMDB search, 4-5 recs with posters
2. **"I'm feeling sad, cheer me up"** → Mood skill activation, comfort-genre recs
3. **"Short movie under 90 minutes"** → Constraint extraction, runtime filtering
4. **"Something for a group of friends"** → Group watch skill, crowd-pleaser recs

### What to Observe:

- **Reasoning panel** — Expand to see profiler output, verification scores, tool calls
- **Posters and streaming info** — Real data from TMDB
- **Analytics tab** — Cost tracking, reasoning stats, architecture overview
- **Profile tab** — Learned preferences update after each conversation

### Enterprise Endpoints to Check:

- `http://localhost:8000/api/health` — Rich dependency health check
- `http://localhost:8000/metrics` — Prometheus metrics
- `http://localhost:8000/api/docs` — Interactive Swagger API docs

---

## Slide 11: Project Stats

| Metric | Value |
|--------|-------|
| **Total Python LOC** | ~3,500 |
| **Total React LOC** | ~1,800 |
| **Backend Endpoints** | 18 (REST) + 1 (WebSocket) |
| **Test Count** | 43 (0 warnings) |
| **Benchmark Score** | 91/100 avg (100% success) |
| **LLM Providers** | 2 (Claude + Gemini) |
| **Agent Roles** | 4 (Profiler, Recommender, Verifier, Optimizer) |
| **Markdown Skills** | 3 (mood, group watch, binge planner) |
| **Enterprise Features** | 12 (JWT, rate limit, metrics, logging, etc.) |
| **Docker Services** | 3 (backend, frontend, nginx) |

---

## Slide 12: Summary

### CineAgent demonstrates:

1. **Agentic AI Mastery** — Multi-agent orchestration, System 2 reasoning, tool use, episodic memory — all built from scratch without LangChain

2. **Enterprise Engineering** — JWT auth, rate limiting, Prometheus metrics, structured logging, input sanitization, CI/CD, Docker deployment

3. **Quantitative Rigor** — 91/100 avg quality score, 100% success rate, 43 automated tests, automated benchmark suite with per-category analysis

4. **Production Readiness** — Real TMDB data, multi-provider fallback with backoff, rich health checks, CORS lockdown, Pydantic validation

**This is not a prototype — it's a production-grade AI system.**

---

*Built for the EAG V2 Capstone by Gowtham*
