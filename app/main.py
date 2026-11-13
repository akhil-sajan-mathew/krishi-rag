import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app import cache, generate
from app.db import connect
from app.embed import embed_query
from app.llm import LLMError
from app.retrieve import Mode, _reranker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load both models at startup so the first user doesn't wait ~30s.
    embed_query("warm up")
    _reranker()
    yield


app = FastAPI(title="Krishi RAG", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    mode: Mode = "hybrid_rerank"


class Citation(BaseModel):
    n: int
    document_id: str
    title: str
    page: int
    url: str | None


class AskResponse(BaseModel):
    answer: str
    found: bool
    uncited: bool
    cached: bool
    citations: list[Citation]
    mode: Mode
    latency_ms: int


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request) -> AskResponse:
    start = time.perf_counter()
    # Behind a reverse proxy, run uvicorn with --proxy-headers so this is the real client IP.
    ip = request.client.host if request.client else "unknown"
    if not cache.allow_request(ip):
        raise HTTPException(status_code=429, detail="Too many questions; try again in an hour.")
    question = req.question.strip()
    key = cache.answer_key(question, req.mode)
    result = cache.get_answer(key)
    cached = result is not None
    if not cached:
        try:
            result = generate.answer(question, req.mode)
        except LLMError as e:
            raise HTTPException(status_code=503, detail=f"LLM unavailable: {e}") from e
        cache.set_answer(key, result)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return AskResponse(**result, cached=cached, mode=req.mode, latency_ms=latency_ms)


@app.get("/health")
def health() -> dict:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
    except Exception as e:  # any DB failure means unhealthy
        raise HTTPException(status_code=503, detail=f"db: {e}") from e
    # Redis is optional (cache and rate limit fail open), so it never makes the API unhealthy.
    return {"db": "ok", "redis": "ok" if cache.ping() else "down"}
