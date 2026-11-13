"""Draft candidate test questions from random chunks. Every draft is checked by hand before it
goes into eval/golden.jsonl; this script only saves typing.

Usage: python -m eval.draft_questions --n 50 --out eval/drafts.jsonl
"""

import argparse
import json
import random
import re

from app.config import settings
from app.db import connect
from app.llm import LLMError, complete

SYSTEM = """You write test questions for a farming Q&A system.
Given one passage, write ONE question a farmer or extension worker might ask that this passage
answers, and the short correct answer taken only from the passage.
Rules: the question must make sense without seeing the passage (name the crop or scheme).
Prefer specific facts: doses, rates, timings, varieties, eligibility, amounts, deadlines.
If the passage has no clear, self-contained fact (tables of contents, references, fragments),
reply exactly SKIP.
Otherwise reply with JSON only: {"question": "...", "answer": "..."}"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="eval/drafts.jsonl")
    args = ap.parse_args()

    with connect() as conn:
        rows = conn.execute(
            """SELECT c.id, c.document_id, c.page_start, c.text FROM chunks c
               WHERE c.config = %s AND c.token_count >= 150 ORDER BY c.id""",
            (settings.chunk_config,),
        ).fetchall()
    random.Random(args.seed).shuffle(rows)

    kept = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for chunk_id, doc_id, page, text in rows:
            if kept >= args.n:
                break
            try:
                reply = complete(SYSTEM, f"Passage:\n{text}")
            except LLMError as e:
                print(f"skip chunk {chunk_id}: {e}")
                continue
            match = re.search(r"\{.*\}", reply, re.DOTALL)
            if reply.strip() == "SKIP" or not match:
                continue
            try:
                qa = json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
            record = {"chunk_id": chunk_id, "doc_id": doc_id, "pages": [page], **qa}
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1
            print(f"{kept:3d} {doc_id} p.{page}: {qa.get('question')}")


if __name__ == "__main__":
    main()
