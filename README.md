# Krishi RAG

A question-answering service for Indian farmers, built on official crop and government-scheme documents. It uses retrieval-augmented generation (RAG): it finds the relevant passages first, then writes an answer that cites the source document and page for every claim. It's built with FastAPI, PostgreSQL with pgvector, Redis and any LLM provider (Claude, OpenAI, Gemini, Groq, OpenRouter, Ollama and other OpenAI-compatible APIs), and it comes with a published evaluation.

**Status:** in progress (Day 2: retrieval and `/ask` API). See [PLAN.md](PLAN.md) for the full build plan.

## Run locally

Needs Python 3.11+, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cp .env.example .env
docker compose up -d db redis
uv sync
uv run python scripts/download.py
uv run python -m app.ingest --config size512_overlap64
uv run uvicorn app.main:app --port 8000
```

Then ask a question:

```bash
curl -X POST localhost:8000/ask -H "content-type: application/json" -d '{"question": "What is the seed rate for bottle gourd?"}'
```

The answer cites its sources as `[1]`, `[2]`, and the response lists the document and page for each number.

## Choosing an LLM

Any provider works. Set these in `.env`:

| Provider | `LLM_PROVIDER` | `LLM_BASE_URL` |
|---|---|---|
| Anthropic (Claude) | `anthropic` | leave empty |
| OpenAI | `openai_compatible` | `https://api.openai.com/v1` |
| Google Gemini | `openai_compatible` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| Groq | `openai_compatible` | `https://api.groq.com/openai/v1` |
| OpenRouter | `openai_compatible` | `https://openrouter.ai/api/v1` |
| Ollama (local, free) | `openai_compatible` | `http://localhost:11434/v1` |

Also set `LLM_MODEL` (the provider's model name) and `LLM_API_KEY` (any text for Ollama).

## Retrieval modes

`/ask` takes an optional `mode`: `vector`, `keyword`, `hybrid` (both, merged with reciprocal rank fusion), or `hybrid_rerank` (default; hybrid followed by a cross-encoder reranker).

Source documents are listed in [data/sources.csv](data/sources.csv). The PDFs themselves are downloaded, not committed.
