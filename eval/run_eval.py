"""Score the system against eval/golden.jsonl.

  python -m eval.run_eval --retrieval-only               # all 4 modes, no LLM, free
  python -m eval.run_eval --mode hybrid_rerank           # full: retrieve + answer + judge
  python -m eval.run_eval --mode hybrid --limit 10       # quick smoke run

Writes eval/results/<timestamp>_<label>.json and appends a row to eval/results/summary.md.
"""

import argparse
import json
import math
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.generate import answer_from_chunks
from app.llm import LLMError, complete
from app.retrieve import MODES, retrieve
from eval.metrics import citation_hit, evidence_recall, mean, percentile, reciprocal_rank

ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "golden.jsonl"
RESULTS = ROOT / "results"
TOP_K = 10  # retrieved for recall@10 / MRR; the first 5 go to the LLM
CONTEXT_K = 5

JUDGE_SYSTEM = """You grade answers from a farming Q&A system. Reply with JSON only:
{"correctness": 0|1|2, "faithful": 0|1, "reason": "<one sentence>"}
correctness: 2 = matches the reference answer's key facts; 1 = partly right or missing a key
fact; 0 = wrong, or says it cannot answer.
faithful: 1 if every claim in the answer is supported by the sources shown; 0 otherwise."""


def load_golden(limit: int | None, types: list[str] | None = None) -> list[dict]:
    rows = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line]
    rows = [r for r in rows if not types or r["type"] in types]
    return rows[:limit] if limit else rows


def judge(item: dict, result: dict, chunks: list[dict]) -> dict:
    sources = "\n\n".join(f"[{i}] {c['text']}" for i, c in enumerate(chunks, start=1))
    prompt = (
        f"Question: {item['question']}\nReference answer: {item['answer']}\n\n"
        f"Answer to grade: {result['answer']}\n\nSources the answer could use:\n{sources}"
    )
    reply = complete(JUDGE_SYSTEM, prompt, role="judge")
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL)  # reasoning models
    match = re.search(r"\{[^{}]*\}", reply, re.DOTALL)
    if not match:
        raise LLMError(f"judge reply had no JSON: {reply[:120]!r}")
    verdict = json.loads(match.group(0))
    return {
        "correctness": int(verdict["correctness"]),
        "faithful": int(verdict["faithful"]),
        "reason": verdict.get("reason", ""),
    }


def score_retrieval(items: list[dict], mode: str, config: str) -> dict:
    rows = []
    for item in items:
        if not item["evidence"]:
            continue
        t = time.perf_counter()
        hits = retrieve(item["question"], mode, top_n=TOP_K, config=config)
        rows.append(
            {
                "id": item["id"],
                "type": item["type"],
                "recall@5": evidence_recall(item["evidence"], hits, 5),
                "recall@10": evidence_recall(item["evidence"], hits, 10),
                "mrr@10": reciprocal_rank(item["evidence"], hits, 10),
                "retrieval_ms": (time.perf_counter() - t) * 1000,
                "top_pages": [f"{h['document_id']}:{h['page']}" for h in hits[:5]],
            }
        )
    return {
        "recall@5": mean([r["recall@5"] for r in rows]),
        "recall@10": mean([r["recall@10"] for r in rows]),
        "mrr@10": mean([r["mrr@10"] for r in rows]),
        "retrieval_p50_ms": percentile([r["retrieval_ms"] for r in rows], 50),
        "by_type": {
            t: mean([r["recall@5"] for r in rows if r["type"] == t])
            for t in sorted({r["type"] for r in rows})
        },
        "rows": rows,
    }


def score_full(items: list[dict], mode: str, config: str) -> dict:
    rows = []
    for n, item in enumerate(items, start=1):
        t = time.perf_counter()
        hits = retrieve(item["question"], mode, top_n=TOP_K, config=config)
        chunks = hits[:CONTEXT_K]
        row = {"id": item["id"], "type": item["type"]}
        try:
            result = answer_from_chunks(item["question"], chunks)
            row["latency_ms"] = (time.perf_counter() - t) * 1000
            row.update(
                answer=result["answer"],
                found=result["found"],
                citations=[f"{c['document_id']}:{c['page']}" for c in result["citations"]],
            )
            if item["evidence"]:
                row["recall@5"] = evidence_recall(item["evidence"], hits, 5)
                row["citation_hit"] = citation_hit(item["evidence"], result["citations"])
                if result["found"]:
                    row.update(judge(item, result, chunks))
                else:
                    row.update(correctness=0, faithful=1, reason="system declined to answer")
            else:
                row["refused_correctly"] = not result["found"]
        except LLMError as e:
            row["error"] = str(e)
        rows.append(row)
        print(f"  {n:2d}/{len(items)} {item['id']} {_short(row)}", flush=True)

    answerable = [r for r in rows if "correctness" in r]
    unanswerable = [r for r in rows if "refused_correctly" in r]
    return {
        "correct_rate": mean([r["correctness"] == 2 for r in answerable]),
        "correctness_avg": mean([r["correctness"] / 2 for r in answerable]),
        "faithfulness": mean([r["faithful"] for r in answerable]),
        "citation_accuracy": mean([r["citation_hit"] for r in answerable]),
        "false_refusal_rate": mean([not r["found"] for r in answerable]),
        "refusal_accuracy": mean([r["refused_correctly"] for r in unanswerable]),
        "recall@5": mean([r["recall@5"] for r in answerable]),
        "latency_p50_ms": percentile([r["latency_ms"] for r in rows if "latency_ms" in r], 50),
        "latency_p95_ms": percentile([r["latency_ms"] for r in rows if "latency_ms" in r], 95),
        "errors": sum("error" in r for r in rows),
        "rows": rows,
    }


def _short(row: dict) -> str:
    if "error" in row:
        return f"ERROR {row['error'][:80]}"
    if "refused_correctly" in row:
        return "refused OK" if row["refused_correctly"] else "ANSWERED (should refuse)"
    return f"correct={row['correctness']} faithful={row['faithful']} cite_hit={row['citation_hit']}"


def _fmt(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{x:.2f}"


def write_results(label: str, summary: dict, meta: dict) -> Path:
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS / f"{stamp}_{label}.json"
    path.write_text(json.dumps({"meta": meta, **summary}, indent=2, default=str), encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="hybrid_rerank", choices=MODES)
    ap.add_argument("--config", default=settings.chunk_config)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--types", nargs="+", choices=["factual", "scheme", "multi_hop", "unanswerable"])
    ap.add_argument("--retrieval-only", action="store_true", help="score retrieval only, no LLM")
    ap.add_argument("--modes", nargs="+", default=list(MODES), choices=MODES, help="with --retrieval-only")
    args = ap.parse_args()
    items = load_golden(args.limit, args.types)
    partial = bool(args.limit or args.types)
    smoke = "smoke_" if partial else ""
    meta = {
        "config": args.config,
        "rerank_model": settings.rerank_model,
        "rerank_pool": settings.rerank_pool,
        "keyword_weight": settings.keyword_weight,
        "embed_model": settings.embed_model,
        "questions": len(items),
    }
    # Partial (--limit/--types) runs are spot checks: keep their JSON, not a summary row.
    summary_md = RESULTS / ("smoke_summary.md" if partial else "summary.md")
    RESULTS.mkdir(exist_ok=True)
    if not summary_md.exists():
        summary_md.write_text(
            "# Eval results\n\n"
            "| when (UTC) | run | recall@5 | recall@10 | MRR@10 | correct | faithful | "
            "citation acc. | refusal acc. | false refusals | p50 latency |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    knobs = (
        f"kw weight {settings.keyword_weight}, pool {settings.rerank_pool}, "
        f"reranker {settings.rerank_model.split('/')[-1]}"
    )

    if args.retrieval_only:
        for mode in args.modes:
            s = score_retrieval(items, mode, args.config)
            path = write_results(f"{smoke}retrieval_{mode}_{args.config}", s, {**meta, "mode": mode})
            print(
                f"{mode:14s} recall@5 {_fmt(s['recall@5'])}  recall@10 {_fmt(s['recall@10'])}  "
                f"MRR@10 {_fmt(s['mrr@10'])}  by type {s['by_type']}  -> {path.name}"
            )
            with summary_md.open("a", encoding="utf-8") as f:
                f.write(
                    f"| {when} | retrieval only: {mode}, {args.config}, {knobs} | {_fmt(s['recall@5'])} | "
                    f"{_fmt(s['recall@10'])} | {_fmt(s['mrr@10'])} | | | | | | "
                    f"{s['retrieval_p50_ms']:.0f} ms |\n"
                )
        return

    meta.update(
        mode=args.mode,
        llm=f"{settings.llm_provider}:{settings.llm_model}",
        judge=f"{settings.judge_provider}:{settings.judge_model}",
    )
    s = score_full(items, args.mode, args.config)
    path = write_results(f"{smoke}full_{args.mode}_{args.config}", s, meta)
    print({k: v for k, v in s.items() if k != "rows"}, "->", path.name)
    with summary_md.open("a", encoding="utf-8") as f:
        f.write(
            f"| {when} | full: {args.mode}, {args.config}, {knobs}, LLM {settings.llm_model}, "
            f"judge {settings.judge_model} | {_fmt(s['recall@5'])} | | | "
            f"{_fmt(s['correct_rate'])} | {_fmt(s['faithfulness'])} | "
            f"{_fmt(s['citation_accuracy'])} | {_fmt(s['refusal_accuracy'])} | "
            f"{_fmt(s['false_refusal_rate'])} | {s['latency_p50_ms']:.0f} ms |\n"
        )


if __name__ == "__main__":
    main()
