# Krishi RAG

A question-answering service for Indian farmers, built on official crop and government-scheme documents. It uses retrieval-augmented generation (RAG): it finds the relevant passages first, then writes an answer that cites the source document and page for every claim. It's built with FastAPI, PostgreSQL with pgvector, Redis and any LLM provider (Claude, OpenAI, Gemini, Groq, OpenRouter, Ollama and other OpenAI-compatible APIs), and it comes with a published evaluation.

**Status:** in progress (Day 1: ingestion). See [PLAN.md](PLAN.md) for the full build plan.

## Run locally

Needs Python 3.11+, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cp .env.example .env
docker compose up -d db redis
uv sync
uv run python scripts/download.py
uv run python -m app.ingest --config size512_overlap64
```

Source documents are listed in [data/sources.csv](data/sources.csv). The PDFs themselves are downloaded, not committed.
