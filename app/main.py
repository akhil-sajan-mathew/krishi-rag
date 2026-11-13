import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import generate
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
    citations: list[Citation]
    mode: Mode
    latency_ms: int


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    start = time.perf_counter()
    try:
        result = generate.answer(req.question.strip(), req.mode)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {e}") from e
    latency_ms = int((time.perf_counter() - start) * 1000)
    return AskResponse(**result, mode=req.mode, latency_ms=latency_ms)


@app.get("/health")
def health() -> dict:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
    except Exception as e:  # any DB failure means unhealthy
        raise HTTPException(status_code=503, detail=f"db: {e}") from e
    return {"db": "ok"}
