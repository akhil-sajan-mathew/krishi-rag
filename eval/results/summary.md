# Eval results

| when (UTC) | run | recall@5 | recall@10 | MRR@10 | correct | faithful | citation acc. | refusal acc. | false refusals | p50 latency |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-13 12:25 | retrieval only: vector, size512_overlap64 (keyword = all words, AND) | 0.81 | 0.91 | 0.62 | | | | | | 64 ms |
| 2026-11-13 12:25 | retrieval only: keyword, size512_overlap64 (keyword = all words, AND) | 0.12 | 0.12 | 0.10 | | | | | | 33 ms |
| 2026-11-13 12:25 | retrieval only: hybrid, size512_overlap64 (keyword = all words, AND) | 0.83 | 0.93 | 0.65 | | | | | | 63 ms |
| 2026-11-13 12:25 | retrieval only: hybrid_rerank, size512_overlap64 (keyword = all words, AND) | 0.87 | 0.93 | 0.74 | | | | | | 957 ms |
| 2026-11-13 12:26 | retrieval only: vector, size512_overlap64 (keyword = any word, OR) | 0.81 | 0.91 | 0.62 | | | | | | 60 ms |
| 2026-11-13 12:26 | retrieval only: keyword, size512_overlap64 (keyword = any word, OR) | 0.53 | 0.68 | 0.39 | | | | | | 52 ms |
| 2026-11-13 12:26 | retrieval only: hybrid, size512_overlap64 (keyword = any word, OR) | 0.72 | 0.85 | 0.57 | | | | | | 82 ms |
| 2026-11-13 12:26 | retrieval only: hybrid_rerank, size512_overlap64 (keyword = any word, OR) | 0.85 | 0.91 | 0.72 | | | | | | 1113 ms |
| 2026-11-13 12:29 | full: hybrid_rerank, size512_overlap64, LLM openai/gpt-oss-120b, judge openai/gpt-oss-20b. **Partial**: 55/60 scored (u06-u10 hit Groq's daily token cap), so refusal acc. is 5/5, not 10/10. Golden v1.0 | 0.85 | | | 0.80 | 0.96 | 0.74 | 1.00 | 0.14 | 17774 ms |
| 2026-11-13 13:08 | retrieval only: hybrid, size512_overlap64, kw weight 0.25, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.82 | 0.93 | 0.63 | | | | | | 86 ms |
| 2026-11-13 13:08 | retrieval only: hybrid_rerank, size512_overlap64, kw weight 0.25, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.88 | 0.94 | 0.73 | | | | | | 968 ms |
| 2026-11-13 13:09 | retrieval only: hybrid, size512_overlap64, kw weight 0.5, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.82 | 0.92 | 0.61 | | | | | | 82 ms |
| 2026-11-13 13:09 | retrieval only: hybrid_rerank, size512_overlap64, kw weight 0.5, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.88 | 0.94 | 0.73 | | | | | | 951 ms |
| 2026-11-13 13:10 | retrieval only: hybrid, size512_overlap64, kw weight 0.0, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.83 | 0.92 | 0.63 | | | | | | 82 ms |
| 2026-11-13 13:10 | retrieval only: hybrid_rerank, size512_overlap64, kw weight 0.0, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.87 | 0.93 | 0.74 | | | | | | 978 ms |
| 2026-11-13 13:14 | retrieval only: vector, size256_overlap32, kw weight 0.5, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.73 | 0.82 | 0.53 | | | | | | 58 ms |
| 2026-11-13 13:14 | retrieval only: keyword, size256_overlap32, kw weight 0.5, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.46 | 0.62 | 0.29 | | | | | | 61 ms |
| 2026-11-13 13:14 | retrieval only: hybrid, size256_overlap32, kw weight 0.5, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.81 | 0.87 | 0.55 | | | | | | 88 ms |
| 2026-11-13 13:14 | retrieval only: hybrid_rerank, size256_overlap32, kw weight 0.5, pool 15, reranker ms-marco-MiniLM-L6-v2 | 0.83 | 0.87 | 0.69 | | | | | | 498 ms |
| 2026-11-13 13:15 | retrieval only: hybrid_rerank, size512_overlap64, kw weight 0.5, pool 10, reranker ms-marco-MiniLM-L6-v2 | 0.88 | 0.91 | 0.73 | | | | | | 665 ms |
| 2026-11-13 13:16 | retrieval only: hybrid_rerank, size512_overlap64, kw weight 0.5, pool 25, reranker ms-marco-MiniLM-L6-v2 | 0.86 | 0.92 | 0.73 | | | | | | 1580 ms |
| 2026-11-13 13:17 | retrieval only: hybrid_rerank, size512_overlap64, kw weight 0.5, pool 15, reranker bge-reranker-base | 0.90 | 0.93 | 0.76 | | | | | | 5568 ms |
| 2026-11-14 13:00 | full: hybrid_rerank, size512_overlap64, kw weight 0.5, pool 15, reranker ms-marco-MiniLM-L6-v2, LLM openai/gpt-oss-120b, judge openai/gpt-oss-20b. Golden v1.1, partial-answer prompt. All 60 questions, scored in two runs (multi-hop + unanswerable, then factual + scheme) to fit Groq's daily cap | 0.86 | | | 0.76 | 0.92 | 0.84 | 0.90 | 0.08 | 18 s |

Notes:
- Golden v1.1 (after the first full run): f13 and m09 rewritten. The reference wrongly named one iron-toxicity-tolerant rice variety; the guide lists several (MO 19, Karishma, Mangala, Karuna).
- Rows before 13:08 used keyword weight 1.0, rerank pool 15 and the MiniLM reranker.
- Day 4 retrieval decisions: keyword weight 0.5, 512-token chunks, MiniLM reranker with a pool of 15. bge-reranker-base scores ~1 question higher but takes ~5.6 s per query on CPU.
- The 14 Nov full row: latency includes waiting out Groq's per-minute rate limit, so it overstates real answer time. Citation accuracy for m04 is understated: its [2†...] citation format was only parsed after this run.
