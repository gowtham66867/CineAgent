import os
import re
import time
import json
import uuid
import sqlite3
import asyncio
import traceback
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from contextlib import asynccontextmanager

from agents.orchestrator import Orchestrator
from core.episodic_memory import EpisodicMemory
from core.model_manager import get_cost_tracker
from core.utils import log_step, log_error, set_trace_id, get_trace_id

# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", "cineagent-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost").split(",")
RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "10/minute")
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")

# ─────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────

REQUEST_COUNT = Counter("cineagent_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("cineagent_request_latency_seconds", "Request latency", ["endpoint"])
LLM_CALLS = Counter("cineagent_llm_calls_total", "Total LLM API calls", ["provider", "role"])
ACTIVE_WS = Counter("cineagent_ws_connections_total", "Total WS connections")

# ─────────────────────────────────────────────────────────
# App Initialization
# ─────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle."""
    global orchestrator, memory, _start_time
    _start_time = datetime.utcnow()
    log_step("Starting CineAgent server...", symbol="🚀")
    orchestrator = Orchestrator()
    memory = EpisodicMemory()
    log_step("CineAgent server ready!", symbol="✅")
    yield
    log_step("CineAgent server shutting down.", symbol="🛑")


app = FastAPI(
    title="CineAgent API",
    description="Enterprise Agentic OTT Content Discovery Engine",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Global state
orchestrator = None
memory = None
_start_time = None


# ─────────────────────────────────────────────────────────
# Middleware: Request Tracing + Metrics
# ─────────────────────────────────────────────────────────

@app.middleware("http")
async def trace_and_metrics_middleware(request: Request, call_next):
    """Attach trace ID to every request, measure latency, log structured output."""
    trace_id = request.headers.get("X-Trace-ID") or uuid.uuid4().hex[:8]
    set_trace_id(trace_id)
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        log_error(f"Unhandled exception: {traceback.format_exc()}")
        response = JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "message": "An unexpected error occurred", "trace_id": trace_id},
        )

    elapsed = time.perf_counter() - start
    response.headers["X-Trace-ID"] = trace_id
    response.headers["X-Response-Time-Ms"] = str(round(elapsed * 1000))

    endpoint = request.url.path
    REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(elapsed)

    return response


# ─────────────────────────────────────────────────────────
# JWT Authentication
# ─────────────────────────────────────────────────────────

def create_token(user_id: str) -> str:
    """Create a JWT token for a user."""
    payload = {
        "sub": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    """Verify a JWT token and return user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(request: Request) -> str:
    """Extract user_id from JWT Bearer token or fall back to 'default'."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = verify_token(token)
        if user_id:
            return user_id
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return "default"


# ─────────────────────────────────────────────────────────
# Input Sanitization
# ─────────────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"system\s*:\s*you\s+are",
    r"<\|im_start\|>",
    r"```system",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

def sanitize_input(text: str) -> str:
    """Strip potential prompt injection patterns and limit length."""
    text = text.strip()
    if len(text) > 2000:
        text = text[:2000]
    if _INJECTION_RE.search(text):
        log_error(f"Prompt injection attempt detected: {text[:100]}")
        raise HTTPException(status_code=400, detail="Invalid input detected")
    return text


# ─────────────────────────────────────────────────────────
# Readiness Guard
# ─────────────────────────────────────────────────────────

def _require_ready():
    if not orchestrator or not memory:
        raise HTTPException(status_code=503, detail="Server not ready")


# ─────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field(default="default", max_length=64)
    session_id: Optional[str] = Field(default=None, max_length=64)

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be blank")
        return v.strip()


class FeedbackRequest(BaseModel):
    user_id: str = Field(default="default", max_length=64)
    title: str = Field(..., min_length=1, max_length=500)
    tmdb_id: Optional[int] = None
    media_type: str = Field(default="movie", pattern="^(movie|tv)$")
    rating: Optional[float] = Field(default=None, ge=0, le=10)
    feedback: Optional[str] = Field(default=None, pattern="^(liked|disliked|watched)?$")


class WatchlistRequest(BaseModel):
    user_id: str = Field(default="default", max_length=64)
    title: str = Field(..., min_length=1, max_length=500)
    tmdb_id: Optional[int] = None
    media_type: str = Field(default="movie", pattern="^(movie|tv)$")
    year: Optional[int] = None
    rating: Optional[float] = None
    genres: List[str] = []
    poster_url: Optional[str] = None
    why: Optional[str] = None


class AuthRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)


# ─────────────────────────────────────────────────────────
# Auth Endpoints
# ─────────────────────────────────────────────────────────

@app.post("/api/auth/token")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_token(request: Request, body: AuthRequest):
    """Get a JWT token for a user. In production, this would verify credentials."""
    token = create_token(body.user_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRY_HOURS * 3600,
        "user_id": body.user_id,
    }


# ─────────────────────────────────────────────────────────
# Core API Endpoints
# ─────────────────────────────────────────────────────────

@app.post("/api/chat")
@limiter.limit(RATE_LIMIT_CHAT)
async def chat(request: Request, body: ChatRequest, user_id: str = Depends(get_current_user)):
    """Main chat endpoint — send a message, get AI recommendations."""
    _require_ready()
    message = sanitize_input(body.message)
    effective_user = body.user_id if body.user_id != "default" else user_id

    result = await orchestrator.handle_message(
        user_id=effective_user,
        message=message,
        session_id=body.session_id,
    )
    return result


@app.get("/api/trending")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def trending(request: Request):
    """Get trending content from TMDB."""
    _require_ready()
    return await orchestrator.get_trending()


@app.get("/api/history/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_history(request: Request, user_id: str):
    """Get conversation history for a user."""
    _require_ready()
    return {"history": orchestrator.get_conversation_history(user_id)}


@app.post("/api/feedback")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def submit_feedback(request: Request, body: FeedbackRequest):
    """Submit feedback on a recommendation (watched, liked, disliked)."""
    _require_ready()
    await memory.add_to_watch_history(
        user_id=body.user_id,
        title=body.title,
        tmdb_id=body.tmdb_id,
        media_type=body.media_type,
        rating=body.rating,
        feedback=body.feedback,
    )
    return {"status": "ok", "message": f"Feedback recorded for '{body.title}'"}


@app.get("/api/preferences/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_preferences(request: Request, user_id: str):
    """Get learned user preferences with confidence scores."""
    _require_ready()
    prefs = await memory.get_preferences(user_id)
    return {"user_id": user_id, "preferences": prefs}


@app.delete("/api/conversation/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def clear_conversation(request: Request, user_id: str):
    """Clear conversation history for a user."""
    _require_ready()
    orchestrator.clear_conversation(user_id)
    return {"status": "ok", "message": "Conversation cleared"}


@app.get("/api/skills")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_skills(request: Request):
    """List all loaded Markdown skills."""
    _require_ready()
    return {"skills": orchestrator.skill_manager.list_skills()}


@app.post("/api/watchlist")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def add_to_watchlist(request: Request, body: WatchlistRequest):
    """Add a movie/show to the user's watchlist."""
    _require_ready()
    await memory.add_to_watchlist(body.user_id, body.model_dump())
    return {"status": "ok", "message": f"Added '{body.title}' to watchlist"}


@app.delete("/api/watchlist/{user_id}/{tmdb_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def remove_from_watchlist(request: Request, user_id: str, tmdb_id: int):
    """Remove a movie/show from the watchlist."""
    _require_ready()
    await memory.remove_from_watchlist(user_id, tmdb_id)
    return {"status": "ok", "message": "Removed from watchlist"}


@app.get("/api/watchlist/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_watchlist(request: Request, user_id: str):
    """Get user's saved watchlist."""
    _require_ready()
    items = await memory.get_watchlist(user_id)
    return {"user_id": user_id, "watchlist": items}


@app.get("/api/reasoning-stats/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_reasoning_stats(request: Request, user_id: str):
    """Get aggregate reasoning analytics for a user."""
    _require_ready()
    stats = await memory.get_reasoning_stats(user_id)
    return {"user_id": user_id, **stats}


@app.get("/api/episodes/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_episodes(request: Request, user_id: str):
    """Get recent episode skeletons (compressed session history)."""
    _require_ready()
    episodes = await memory.get_recent_episodes(user_id, limit=20)
    return {"user_id": user_id, "episodes": episodes}


@app.get("/api/watch-history/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_watch_history(request: Request, user_id: str):
    """Get watch history with ratings and feedback."""
    _require_ready()
    history = await memory.get_watch_history(user_id, limit=50)
    return {"user_id": user_id, "history": history}


@app.get("/api/cost-tracker")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def cost_tracker(request: Request):
    """Get LLM token usage and cost tracking breakdown."""
    return get_cost_tracker()


# ─────────────────────────────────────────────────────────
# Health & Observability
# ─────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Rich health check — reports status of all dependencies."""
    checks = {}

    # Database
    try:
        db_path = memory.db_path if memory else None
        if db_path:
            with sqlite3.connect(db_path) as conn:
                conn.execute("SELECT 1")
            checks["database"] = {"status": "ok"}
        else:
            checks["database"] = {"status": "unavailable"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}

    # LLM providers
    checks["llm_providers"] = {
        "anthropic": "configured" if os.getenv("ANTHROPIC_API_KEY") else "missing",
        "gemini": "configured" if os.getenv("GEMINI_API_KEY") else "missing",
    }

    # TMDB
    checks["tmdb"] = "configured" if os.getenv("TMDB_API_KEY") else "missing"

    # Orchestrator
    checks["orchestrator"] = "ready" if orchestrator else "not_initialized"

    # Skills
    if orchestrator:
        checks["skills_loaded"] = len(orchestrator.skill_manager.list_skills())

    # Cost tracker summary
    ct = get_cost_tracker()
    checks["llm_usage"] = {
        "total_requests": ct["total_requests"],
        "total_cost_usd": round(ct["total_cost_usd"], 4),
        "fallbacks_triggered": ct["fallbacks_triggered"],
    }

    all_ok = (
        checks["database"].get("status") == "ok"
        and checks["orchestrator"] == "ready"
    )

    return {
        "status": "healthy" if all_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "uptime_seconds": round((datetime.utcnow() - _start_time).total_seconds()) if _start_time else 0,
        "checks": checks,
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    from starlette.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ─────────────────────────────────────────────────────────
# WebSocket (Real-time Chat)
# ─────────────────────────────────────────────────────────

class ConnectionManager:
    """Manages WebSocket connections with per-user isolation."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        ACTIVE_WS.inc()
        log_step(f"WebSocket connected: {user_id}", symbol="🔗")

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        log_step(f"WebSocket disconnected: {user_id}", symbol="🔌")

    async def send_json(self, user_id: str, data: dict):
        ws = self.active_connections.get(user_id)
        if ws:
            await ws.send_json(data)


ws_manager = ConnectionManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "").strip()

            if not message:
                await ws_manager.send_json(user_id, {"type": "error", "message": "Empty message"})
                continue

            if len(message) > 2000:
                await ws_manager.send_json(user_id, {"type": "error", "message": "Message too long (max 2000 chars)"})
                continue

            trace_id = set_trace_id()

            await ws_manager.send_json(user_id, {
                "type": "status",
                "message": "Analyzing your request...",
                "phase": "perception",
                "trace_id": trace_id,
            })

            try:
                result = await orchestrator.handle_message(
                    user_id=user_id,
                    message=message,
                    session_id=data.get("session_id"),
                )
                result["trace_id"] = trace_id
                await ws_manager.send_json(user_id, result)
            except Exception as e:
                log_error(f"Chat processing error: {e}")
                await ws_manager.send_json(user_id, {
                    "type": "error",
                    "message": "Sorry, something went wrong processing your request.",
                    "trace_id": trace_id,
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
    except Exception as e:
        log_error(f"WebSocket error for {user_id}: {e}")
        ws_manager.disconnect(user_id)


# ─────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
