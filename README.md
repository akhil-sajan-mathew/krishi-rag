# Krishi RAG

[![CI](https://github.com/akhil-sajan-mathew/krishi-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/akhil-sajan-mathew/krishi-rag/actions/workflows/ci.yml)

A question-answering service for Indian farmers, built on official crop and government-scheme documents. It uses retrieval-augmented generation (RAG): it finds the relevant passages first, then writes an answer that cites the source document and page for every claim. It's built with FastAPI, PostgreSQL with pgvector, Redis and any LLM provider (Claude, OpenAI, Gemini, Groq, OpenRouter, Ollama and other OpenAI-compatible APIs), and it comes with a published evaluation.

**Status:** in progress (Day 6: production setup ready; not yet deployed). See [PLAN.md](PLAN.md) for the full build plan.

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

Open http://localhost:8000 for the web page, or ask from the command line:

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

## Deploying

The production setup is a Docker image (CPU-only PyTorch, models baked in, runs as a non-root user) plus Caddy for automatic HTTPS. Only Caddy is reachable from outside; the API, Postgres and Redis are not. It runs on any Linux server with 2 GB of RAM:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Step-by-step guide (server, domain, `.env`, loading documents, updates): [docs/deploy.md](docs/deploy.md).

## Caching and rate limits

- Answers are cached in Redis for 7 days. The cache key covers the question (case and spacing ignored) and every setting that changes answers: mode, chunk size, fusion weight, reranker, LLM, and the prompt itself. A repeat question returns in about 2 ms instead of several seconds; the response says `"cached": true`.
- Each IP address may ask `RATE_LIMIT_PER_HOUR` questions per hour (default 20; 0 turns it off). Further requests get HTTP 429.
- Both fail open: if Redis is down, `/ask` still answers (uncached, unlimited) and `/health` reports `"redis": "down"`.

## Retrieval modes

`/ask` takes an optional `mode`: `vector`, `keyword`, `hybrid` (both, merged with reciprocal rank fusion), or `hybrid_rerank` (default; hybrid followed by a cross-encoder reranker).

## Evaluation

[eval/golden.jsonl](eval/golden.jsonl) has 60 questions: 30 factual, 10 government-scheme, 10 multi-hop (the answer needs two pages) and 10 unanswerable (the topic is not in the documents, so the right reply is to decline). Factual and scheme questions were drafted by an LLM from random chunks (`eval/draft_questions.py`, raw drafts in `eval/drafts.jsonl`), then each one was checked against its source page; 2 of 50 drafts were wrong and dropped, most were reworded the way a farmer would ask. Multi-hop and unanswerable questions were written by hand, and every unanswerable topic was confirmed to have no match in the documents.

```bash
uv run python -m eval.run_eval --retrieval-only        # all retrieval modes, no LLM needed
uv run python -m eval.run_eval --mode hybrid_rerank    # retrieve, answer, and grade with a judge LLM
```

First results ([full table](eval/results/summary.md)):

Retrieval (50 answerable questions; recall@5 = share of evidence pages found in the top 5):

| Setup | recall@5 | MRR@10 | median time |
|---|---|---|---|
| vector only | 0.81 | 0.62 | 0.06 s |
| keyword only | 0.53 | 0.39 | 0.05 s |
| hybrid, equal weights | 0.72 | 0.57 | 0.08 s |
| hybrid, keyword weight 0.5 | 0.82 | 0.61 | 0.08 s |
| **hybrid (weight 0.5) + MiniLM rerank** (default) | **0.88** | **0.73** | 0.95 s |
| same with bge-reranker-base | 0.90 | 0.76 | 5.6 s |
| default setup on 256-token chunks | 0.83 | 0.69 | 0.5 s |

What the experiments showed:
- Keyword search on its own is weak on conversational questions, and with equal weight it drags hybrid below vector alone. At half weight it no longer hurts; with the reranker on it adds little either way.
- The reranker is the biggest single gain (MRR 0.61 to 0.73). The larger bge reranker adds about one more question for six times the wait.
- 256-token chunks lose to 512-token chunks even when given the same amount of text.
- With 50 questions, one question is 0.02 of recall, so differences under about 0.04 are noise.

Full pipeline, all 60 questions, `gpt-oss-120b` answering and `gpt-oss-20b` judging (14 Nov, default settings):

| | Day 3 (55 questions) | Now (60 questions) |
|---|---|---|
| Fully correct | 80% | 76% |
| Average score (half credit for partly right) | 80% | **81%** |
| Faithful to sources | 96% | 92% |
| Cites the right page | 74% | **84%** |
| Answerable questions wrongly declined | 14% | **8%** |
| Off-topic questions correctly declined | 5 of 5 | 9 of 10 |

By type, average score: factual 87%, scheme 90%, multi-hop 55% (was 40%).

What changed and what it means:
- The prompt now answers the covered part of a two-part question instead of declining it. Multi-hop declines went from 5 of 10 to 0, so more answers get partial credit; fewer are fully correct, and the judge marks some "this part isn't covered" claims as unfaithful when the missing half was in the documents but not retrieved. Overall the trade is about even, and the answers are more useful.
- Citation accuracy rose mainly from parsing two gpt-oss citation styles (`【2】`, `[2†...]`).
- The one off-topic miss (nano urea) said plainly that nano urea isn't covered, then gave plain-urea spray rates. It counts as a failure because it didn't decline outright.

What it gets wrong today:
- **Retrieval misses:** in 4 of the 5 wrong factual/scheme answers, the right page wasn't in the top 5, so the model correctly declined. Better retrieval would fix these, not a better prompt.
- **Reading errors:** in a few answers the right page was retrieved and the model still missed or misread the fact (m06, m08, f13).
- **Retrieval for two-topic questions:** one query rarely fetches both topics (m07 got neither page). Splitting the question into two searches is a planned stretch goal.

Source documents are listed in [data/sources.csv](data/sources.csv). The PDFs themselves are downloaded, not committed.
