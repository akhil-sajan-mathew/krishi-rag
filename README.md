# Krishi RAG

A question-answering service for Indian farmers, built on official crop and government-scheme documents. It uses retrieval-augmented generation (RAG): it finds the relevant passages first, then writes an answer that cites the source document and page for every claim. It's built with FastAPI, PostgreSQL with pgvector, Redis and any LLM provider (Claude, OpenAI, Gemini, Groq, OpenRouter, Ollama and other OpenAI-compatible APIs), and it comes with a published evaluation.

**Status:** in progress (Day 3: evaluation). See [PLAN.md](PLAN.md) for the full build plan.

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

## Evaluation

[eval/golden.jsonl](eval/golden.jsonl) has 60 questions: 30 factual, 10 government-scheme, 10 multi-hop (the answer needs two pages) and 10 unanswerable (the topic is not in the documents, so the right reply is to decline). Factual and scheme questions were drafted by an LLM from random chunks (`eval/draft_questions.py`, raw drafts in `eval/drafts.jsonl`), then each one was checked against its source page; 2 of 50 drafts were wrong and dropped, most were reworded the way a farmer would ask. Multi-hop and unanswerable questions were written by hand, and every unanswerable topic was confirmed to have no match in the documents.

```bash
uv run python -m eval.run_eval --retrieval-only        # all retrieval modes, no LLM needed
uv run python -m eval.run_eval --mode hybrid_rerank    # retrieve, answer, and grade with a judge LLM
```

First results ([full table](eval/results/summary.md)):

| Retrieval mode | recall@5 | MRR@10 |
|---|---|---|
| vector | 0.81 | 0.62 |
| keyword | 0.53 | 0.39 |
| hybrid (RRF) | 0.72 | 0.57 |
| **hybrid + rerank** | **0.85** | **0.72** |

Full pipeline with `gpt-oss-120b` answering and `gpt-oss-20b` judging (55 of 60 questions; the free tier's daily token cap stopped the last 5): **80% fully correct, 96% faithful to sources, 74% cite the right page, 5 of 5 unanswerable questions correctly declined.**

What it gets wrong today:
- **Multi-hop questions:** when the sources cover only one half, the model often declines the whole question instead of answering the half it can (5 of 10).
- **Plain hybrid is worse than vector alone:** keyword hits dilute good vector hits in the fusion; the reranker recovers it. Weighted fusion is the next experiment.

Source documents are listed in [data/sources.csv](data/sources.csv). The PDFs themselves are downloaded, not committed.
