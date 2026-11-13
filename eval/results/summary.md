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

Notes:
- Golden v1.1 (after the first full run): f13 and m09 rewritten. The reference wrongly named one iron-toxicity-tolerant rice variety; the guide lists several (MO 19, Karishma, Mangala, Karuna).
