# Krishi RAG: Build Plan

> A question-answering service for Indian farmers. It answers questions from official crop and scheme documents and cites the source page for every claim. Its evaluation numbers are published in the README.

**Status:** planning · **Target:** 6–8 part-time days

---

## 0. Goals

| Goal | How |
|---|---|
| Retrieval-augmented answers | Full retrieval pipeline on pgvector. LlamaIndex for ingestion, plus a hand-written retriever |
| Measured quality | A test set of questions with known answers, retrieval metrics, an LLM judge, and a before/after results table |
| Runs in the cloud | Runs live on AWS Lightsail or EC2 behind HTTPS |
| Fast repeat queries | Redis caches answers and query embeddings |
| One datastore | Postgres schema, pgvector indexes, full-text search |
| Reproducible | Docker Compose for local and production, GitHub Actions for tests and a small eval run |
| Public and usable | Public repo, live URL, demo GIF, results table |

**Summary:** a RAG system over Indian agriculture documents, with a 60-question test set that measures how much each retrieval change improves recall@5.

---

## 1. Scope

### In scope (version 1)
- Ingest about 30–60 public English PDFs: crop practice guides and government scheme guidelines.
- `POST /ask`: takes a question, returns an answer with citations (document, page, and quoted text).
- Hybrid retrieval combining vector search and keyword search, followed by a reranker.
- An evaluation harness that runs from the command line and writes results to `eval/results/`.
- Redis cache, Docker Compose, GitHub Actions, and a live AWS deployment.
- A minimal web UI: one HTML page with a question box and the answer with citations.

### Out of scope (say no until v1 ships)
- Hindi and other regional languages. This is the strongest stretch goal (section 13).
- User accounts, chat history, multi-turn conversation.
- Agents and tool use. Single retrieve-then-generate is enough.
- Fine-tuning.
- A React frontend. Add it only if time is left over.
- Kubernetes, Terraform. Use one box and Docker Compose.

---

## 2. Architecture

```
            ┌────────────┐
 PDFs ───►  │  ingest.py │ parse → clean → chunk → embed
            └─────┬──────┘
                  ▼
        ┌───────────────────┐
        │ Postgres+pgvector │  documents, chunks(embedding vector, tsvector)
        └─────────┬─────────┘
                  │
 user ─► FastAPI /ask ─► Redis cache? ──hit──► answer
                  │ miss
                  ▼
          retrieve (vector top-20 ∪ BM25 top-20)
                  ▼
          reciprocal rank fusion → rerank (cross-encoder) → top-5
                  ▼
          LLM (any provider; numbered chunks, answer cites [n])
                  ▼
          answer + citations ─► cache ─► user
```

`eval/` calls the same `retrieve()` and `answer()` functions directly, without HTTP, so it measures exactly the code that ships.

---

## 3. Tech choices

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Best ML ecosystem |
| API | FastAPI + Uvicorn | Async, Pydantic validation, auto-generated OpenAPI docs |
| Vector store | Postgres 16 + **pgvector** | One database for metadata, vectors and full-text search |
| Keyword search | Postgres `tsvector` + `ts_rank_cd` | BM25-like ranking with no extra service |
| Embeddings | `BAAI/bge-small-en-v1.5` (384 dimensions) via `sentence-transformers` | Free, runs locally on CPU, strong for its size. Keeps embeddings independent of the LLM provider |
| Reranker | `BAAI/bge-reranker-base` cross-encoder | Large precision gain for little code. Gives you a clear before/after result |
| Ingestion | **LlamaIndex** readers + `SentenceSplitter` | Mature chunking with page tracking. Retrieval stays hand-written so every step is visible |
| PDF parsing | `pymupdf` (fitz) | Fast, keeps page numbers, which citations need |
| LLM | **Any provider**, picked in `.env`: `LLM_PROVIDER=anthropic` (official `anthropic` SDK) or `LLM_PROVIDER=openai_compatible` + `LLM_BASE_URL` (official `openai` SDK; covers OpenAI, Gemini, Groq, OpenRouter, Together, Mistral, DeepSeek, Ollama, LM Studio). Model in `LLM_MODEL` | No lock-in. One small adapter (`app/llm.py`) with a single `complete(system, user) -> text` function |
| Judge LLM | Same adapter, separate `JUDGE_PROVIDER` / `JUDGE_MODEL` / `JUDGE_BASE_URL` | Faithfulness and correctness grading. A different model from the generator reduces self-grading bias |
| Cache | Redis 7 | Answer cache (key = hash of question + config). Rate limiting is a stretch goal |
| Tests | pytest, httpx `TestClient` | Unit tests plus API tests |
| CI | GitHub Actions | Lint (ruff), tests, and a small 10-question evaluation on PRs |
| Deploy | AWS Lightsail (or EC2 t3.small) + Docker Compose + Caddy | Simplest real cloud setup. Caddy handles HTTPS automatically |

**LLM cost check:** an answer sends about 5 chunks × 400 tokens ≈ 2–3k input tokens, so a full 60-question eval run is roughly 200k input tokens. On most hosted models that's cents to a couple of dollars; a local Ollama model costs nothing but is slow on CPU and follows the citation format less reliably. Every results file records the provider and model that produced it.

---

## 4. Data plan

### Sources (check availability and terms on Day 1, before writing any code)
1. **Crop practice guides:** ICAR institute publications and state agricultural university "Package of Practices" documents (for example TNAU Agritech portal, Kerala Agricultural University, PAU). Pick about 5 crops: rice, wheat, cotton, tomato, banana.
2. **Government scheme guidelines:** operational guidelines for PM-KISAN, PMFBY (crop insurance), Soil Health Card, and KCC (Kisan Credit Card).
3. **Pest and disease advisories:** ICAR / NCIPM advisories for the same crops.

### Rules
- English-language PDFs that actually contain text. If a PDF is a scan with no text layer, skip it.
- Keep `data/sources.csv` with these columns: `doc_id, title, publisher, url, crop_or_scheme, downloaded_on, license_note`.
- **Do not commit the PDFs.** Commit `sources.csv` and a `scripts/download.py` that fetches them. This keeps the repo small and avoids redistribution questions.
- Target: 30–60 documents, about 3–10k chunks. That's small enough for CPU embedding in minutes.

---

## 5. Database schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id            TEXT PRIMARY KEY,          -- doc_id from sources.csv
  title         TEXT NOT NULL,
  publisher     TEXT,
  url           TEXT,
  category      TEXT,                      -- crop | scheme | advisory
  page_count    INT,
  ingested_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chunks (
  id            BIGSERIAL PRIMARY KEY,
  document_id   TEXT REFERENCES documents(id) ON DELETE CASCADE,
  page_start    INT NOT NULL,
  page_end      INT NOT NULL,
  chunk_index   INT NOT NULL,
  text          TEXT NOT NULL,
  token_count   INT,
  embedding     vector(384),
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
  config        TEXT NOT NULL              -- e.g. "size512_overlap64" so experiments can coexist
);

CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks USING gin (tsv);
CREATE INDEX ON chunks (config);
```

The `config` column lets you store several chunking strategies side by side and compare them in the eval, without having to re-ingest.

---

## 6. Repo layout

```
krishi-rag/
├── PLAN.md
├── README.md
├── docker-compose.yml          # api, db (pgvector/pgvector:pg16), redis
├── docker-compose.prod.yml     # + caddy
├── Dockerfile
├── pyproject.toml
├── .env.example                # DATABASE_URL, REDIS_URL, LLM_PROVIDER/MODEL/BASE_URL/API_KEY, JUDGE_* (same)
├── data/
│   ├── sources.csv
│   └── raw/                    # gitignored PDFs
├── migrations/001_init.sql
├── app/
│   ├── main.py                 # FastAPI app, /ask, /health, static UI
│   ├── config.py               # pydantic-settings
│   ├── db.py                   # psycopg pool
│   ├── ingest.py               # parse → chunk → embed → insert
│   ├── retrieve.py             # vector, keyword, fusion, rerank
│   ├── llm.py                  # provider adapter: anthropic | openai_compatible
│   ├── generate.py             # prompt with numbered sources, parse [n] citations
│   ├── cache.py                # Redis wrapper
│   └── static/index.html
├── eval/
│   ├── golden.jsonl            # the test set
│   ├── run_eval.py             # CLI: --config, --retriever, --limit
│   ├── metrics.py
│   └── results/                # one JSON + one markdown summary per run (committed)
├── scripts/download.py
├── tests/
│   ├── test_chunking.py
│   ├── test_retrieve.py
│   ├── test_metrics.py
│   └── test_api.py
└── .github/workflows/ci.yml
```

---

## 7. Component details

### 7.1 Ingestion (`app/ingest.py`)
1. Read the PDF with pymupdf, page by page, keeping page numbers.
2. Clean the text: remove repeated headers and footers (lines that appear on more than 50% of pages), fix words hyphenated across line breaks, and collapse whitespace.
3. Chunk with LlamaIndex `SentenceSplitter`, tracking page spans. Two configs to compare:
   - `size512_overlap64`
   - `size256_overlap32`
4. Embed in batches of 64 with bge-small. Normalize the vectors, and prefix nothing for passages (bge uses a query instruction only on the query side).
5. Upsert: rerunning ingestion must be idempotent. Delete the document's chunks for that config, then insert.
6. CLI: `python -m app.ingest --config size512_overlap64`.

### 7.2 Retrieval (`app/retrieve.py`)
- `vector_search(q, k=20)`: embed the query with the bge query instruction, then `ORDER BY embedding <=> $1 LIMIT k`.
- `keyword_search(q, k=20)`: `websearch_to_tsquery('english', q)` ranked by `ts_rank_cd`.
- `fuse(lists, k=60)`: reciprocal rank fusion, `score = Σ 1/(k + rank)`.
- `rerank(q, chunks, top_n=5)`: cross-encoder scores, sorted.
- `retrieve(q, mode)`, where `mode ∈ {vector, keyword, hybrid, hybrid_rerank}`. The eval sweeps all four.

### 7.3 LLM adapter (`app/llm.py`) and generation (`app/generate.py`)
- `app/llm.py` exposes one function, `complete(system, user, role="llm") -> str`. `role` picks the `LLM_*` or `JUDGE_*` settings.
  - `anthropic` backend: official `anthropic` SDK. Don't send `temperature` (current Claude API versions reject it). Check `stop_reason` before reading `content`; treat `refusal` as "no answer".
  - `openai_compatible` backend: official `openai` SDK with `base_url` and `api_key` from env. Ollama needs no real key (send any string).
  - Provider-only knobs (Claude `effort`, etc.) stay inside the backend. Nothing else in the code knows which provider is in use.
  - Before writing each backend, read that SDK's docs for exact call shapes. Don't write it from memory.
- **Citations are prompt-based, so they work with every provider:**
  - The user message lists the chunks as `[1] (doc title, p.12) <text>` … `[5] …`, then the question.
  - The system prompt says: answer only from the numbered sources, put `[n]` after each claim, and if the sources don't contain the answer, reply exactly `NOT_FOUND`. Under 150 words, plain language, units spelled out.
  - `generate.py` parses `[n]` markers, **drops any number that isn't a real source**, and maps the rest to `{document_id, title, page, url}`. An answer with zero valid citations is flagged `uncited: true`.
- The eval's citation-accuracy metric measures how well each model follows this format.

### 7.4 API (`app/main.py`)
| Endpoint | Request | Response |
|---|---|---|
| `POST /ask` | `{question: str (3–500 chars), mode?: str}` | `{answer, citations[], mode, cached: bool, latency_ms}` |
| `GET /health` | n/a | `{db: ok, redis: ok}` |
| `GET /` | n/a | static UI |

- Validate input length with Pydantic. Return 422 on bad input and 503 if the LLM is unavailable.
- Log each request (question hash, mode, latency, cache hit) as one JSON line on stdout.

### 7.5 Cache (`app/cache.py`)
- Key: `sha256(normalized_question + mode + LLM_MODEL + chunk_config)`. TTL 7 days.
- Measure the hit rate and latency difference and put them in the README (for example "p50 2.8s → 15ms on cache hit").

---

## 8. Evaluation

### 8.1 Test set: `eval/golden.jsonl`
One JSON object per line:
```json
{"id": "q017", "question": "What is the recommended seed rate for transplanted rice?", "answer": "...", "doc_id": "icar_rice_pop", "pages": [12], "type": "factual"}
```
- **60 questions**, mixed as follows:
  - 30 factual (single fact, one page)
  - 10 scheme eligibility ("Can a tenant farmer get PM-KISAN?")
  - 10 multi-hop (the answer needs 2 chunks)
  - 10 **unanswerable** (not in the corpus). The correct behaviour is to decline.
- How to build it: have an LLM draft question/answer pairs from random chunks, then **check and edit every one by hand**. Write at least 15 yourself, phrased the way a farmer would ask. State this method in the README.
- Freeze it after Day 3. Changing the test set after seeing results is cheating, so add a version number if you must change it.

### 8.2 Metrics (`eval/metrics.py`)
| Metric | What it measures | How |
|---|---|---|
| Recall@5 | Did the correct page reach the top 5? | Hit if any retrieved chunk overlaps `(doc_id, pages)` |
| MRR@10 | How high the first correct chunk ranks | 1/rank |
| Faithfulness | Is every claim supported by the cited chunks? | LLM judge, 0/1 per answer, with a short reason |
| Correctness | Does the answer match the reference? | LLM judge, 0/1/2 |
| Citation accuracy | Do the citations point to the correct page? | Rule-based |
| Refusal accuracy | Does it decline the 10 unanswerable questions? | Rule-based + judge |
| Latency p50/p95 | Speed | Timer |
| Cost per question | Money | Token counts from `response.usage` × price |

Unit-test `metrics.py` with hand-made cases (`tests/test_metrics.py`).

### 8.3 Experiments to run (each one becomes a row in the README table)
| # | Change | Expected story |
|---|---|---|
| E1 | Vector only, size 512 | Baseline |
| E2 | Keyword only | Good at exact terms (scheme names), weak on paraphrased questions |
| E3 | Hybrid (RRF) | Beats both |
| E4 | Hybrid + rerank | Best precision |
| E5 | E4 with size-256 chunks | Smaller chunks: does precision or context win? |
| E6 | E4 with two or three different LLMs (e.g. one hosted, one local) | Quality, citation accuracy, cost and latency per model |

Run: `python -m eval.run_eval --mode hybrid_rerank --config size512_overlap64`, which writes `eval/results/<timestamp>_<mode>.json` and appends to `eval/results/summary.md`.

**Be honest about results.** If an experiment doesn't help, report it anyway. A table that shows losses is more trustworthy.

---

## 9. Testing & CI

- `tests/test_chunking.py`: page spans are preserved, and no chunk is empty or too long.
- `tests/test_retrieve.py`: RRF fusion math on fixed inputs, and keyword search on a 3-document test database.
- `tests/test_api.py`: `/ask` validation (422), `/health`, and a cache hit on the second call (LLM mocked).
- `tests/test_metrics.py`: recall and MRR on hand-made cases.
- CI (`.github/workflows/ci.yml`):
  1. `ruff check`
  2. `pytest` with a pgvector service container and a Redis service container
  3. On PRs only, and only if the `LLM_API_KEY` secret exists: a 10-question eval smoke run that fails if recall@5 drops below a threshold
- Put the CI badge in the README.

---

## 10. Deployment (AWS)

1. Lightsail instance with 2 GB RAM (or EC2 t3.small) running Ubuntu. Open ports 80 and 443 only.
2. Install Docker. `git clone`, then copy `.env` by hand. **Never commit secrets.**
3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
4. Caddy reverse-proxies to the API, with automatic HTTPS on a free subdomain (for example duckdns) or your own domain.
5. Run ingestion once on the server. Postgres data lives in a named volume.
6. Protect your API bill: a Redis rate limit (for example 20 questions per IP per hour) and a hard monthly spend limit in your LLM provider's dashboard.
7. Write the steps in `docs/deploy.md`. Keep them simple enough to repeat from scratch.

**Watch out:** the reranker and embedding models need about 1.5 GB of RAM. If 2 GB is tight, add swap, or drop the reranker in production and say so.

---

## 11. Day-by-day plan (each day ends with a "done when")

| Day | Work | Done when |
|---|---|---|
| **1** | Check sources, write `sources.csv`, `download.py`, Docker Compose with db and redis, migration, `ingest.py` | `SELECT count(*) FROM chunks` returns thousands of rows, and every chunk has a page number |
| **2** | `retrieve.py` (vector, keyword, RRF), `generate.py` with citations, `/ask` endpoint | `curl /ask` returns an answer with a correct page citation for 5 hand-picked questions |
| **3** | Build and freeze `golden.jsonl` (60 questions), `metrics.py` + tests, `run_eval.py` | Baseline E1 numbers are recorded in `eval/results/summary.md` |
| **4** | Reranker, size-256 config, run E2–E6 | The full experiment table is filled in. You can say which change helped most and why |
| **5** | Redis cache, rate limit, pytest suite, GitHub Actions | CI is green. Measured cache hit vs miss latency |
| **6** | AWS deployment with Caddy and HTTPS, `docs/deploy.md` | The public URL answers a question from your phone |
| **7** | README: diagram, results table, demo GIF, "what I learned", limitations | Someone new understands the project in 60 seconds |
| **8** | Buffer for overruns and a stretch goal | — |

---

## 12. README outline

1. One-sentence pitch + live link + CI badge + a 20-second demo GIF
2. Architecture diagram
3. **Results table** (section 8.3) with the headline number in bold
4. How the evaluation works (test set method, metrics, honest caveats)
5. Run it locally in 3 commands
6. Design decisions: why pgvector, why hybrid search, why reranking
7. Limitations and next steps
8. Data sources and licence notes

---

## 13. Stretch goals (only after Day 7)

1. **Hindi or a regional language:** swap in `BAAI/bge-m3` (multilingual), add 10 Hindi test questions, and report cross-lingual recall. This is the most useful add-on for real farmers.
2. React/Next.js UI with streaming answers.
3. A LangChain version of the retriever behind a flag, with a short comparison in the README.
4. Query rewriting: ask the LLM to rephrase a vague farmer question before retrieval, then measure the effect.
5. Observability: per-request token and cost dashboard.

---

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| PDFs are scanned images (no text) | Filter them on Day 1. OCR is out of scope |
| Tables in PDFs parse badly (dosage tables) | Accept it for v1 and list it under limitations. A stretch fix is pymupdf table extraction |
| LLM-generated test set is too easy | 15+ questions written by hand, 10 unanswerable, a multi-hop slice |
| API bill surprise | Spend limit in Console, rate limit, cache, small CI eval |
| Low RAM on a cheap server | Swap, or turn the reranker off in production |
| Scope creep | Section 1 "out of scope" list. Nothing from section 13 before Day 7 |

---

## 15. Definition of done (v1)

- [ ] Live HTTPS URL answers questions with page citations
- [ ] `eval/results/summary.md` has E1–E6 with real numbers
- [ ] CI green, badge in README
- [ ] Fresh clone → `docker compose up` → ingest → working `/ask` in under 15 minutes, following the README
- [ ] No secrets or PDFs committed
