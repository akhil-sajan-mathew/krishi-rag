"""Download the source PDFs listed in data/sources.csv into data/raw/<doc_id>.pdf.

Usage: python scripts/download.py [--force]
"""

import csv
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources.csv"
RAW = ROOT / "data" / "raw"


def download(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (krishi-rag downloader)"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    if not data.startswith(b"%PDF"):
        raise ValueError("response is not a PDF")
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(dest)  # no half-written PDFs if interrupted
    return len(data)


def main() -> int:
    force = "--force" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    failed = 0
    with SOURCES.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dest = RAW / f"{row['doc_id']}.pdf"
            if dest.exists() and not force:
                print(f"skip   {row['doc_id']} (exists)")
                continue
            try:
                size = download(row["url"], dest)
                print(f"ok     {row['doc_id']} ({size / 1e6:.1f} MB)")
            except (OSError, ValueError) as e:  # network/HTTP/SSL errors, or not a PDF; keep going
                failed += 1
                print(f"FAILED {row['doc_id']}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
