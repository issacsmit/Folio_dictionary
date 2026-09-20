#!/usr/bin/env python3
"""Longman bilingual scan PDF → OCR → structured sample DB."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from folio_ocr.config import (  # noqa: E402
    ALL_OCR_PAGES,
    OUTPUT_DIR,
    SAMPLE_PAGES,
    ensure_output_dirs,
    find_main_pdf,
)
from folio_ocr.db import build_db  # noqa: E402
from folio_ocr.extract import extract_pages  # noqa: E402
from folio_ocr.ocr import ocr_pages  # noqa: E402
from folio_ocr.parse import parse_all  # noqa: E402
from folio_ocr.query import format_lookup, lookup  # noqa: E402
from folio_ocr.revise_sample import apply as apply_revisions  # noqa: E402


def cmd_extract(force: bool) -> None:
    recs = extract_pages(ALL_OCR_PAGES, force=force)
    n_ok = sum(1 for r in recs if r.get("status") == "ok")
    print(f"extract: {n_ok}/{len(recs)} ok")


def cmd_ocr(force: bool) -> None:
    summaries = ocr_pages(ALL_OCR_PAGES, force=force)
    n_ok = sum(1 for r in summaries if r.get("status") == "ok")
    n_err = sum(1 for r in summaries if r.get("status") != "ok")
    print(f"ocr: {n_ok} ok, {n_err} failed")


def cmd_parse() -> None:
    entries = parse_all()
    sample = [e for e in entries if e.get("role") == "sample"]
    complete = [e for e in sample if e.get("complete")]
    print(
        f"parse: sample_entries={len(sample)} complete={len(complete)} "
        f"incomplete={len(sample) - len(complete)}"
    )


def cmd_revise() -> None:
    path = apply_revisions()
    print(f"revised jsonl: {path}")


def cmd_db() -> None:
    path = build_db()
    print(f"sqlite: {path}")


def cmd_query(word: str) -> None:
    print(format_lookup(lookup(word)))


def write_env() -> None:
    ensure_output_dirs()
    import numpy
    import PIL
    import pymupdf
    import rapidocr

    try:
        import onnxruntime as ort

        providers = ort.get_available_providers()
        ort_ver = ort.__version__
    except Exception as exc:  # noqa: BLE001
        providers, ort_ver = [str(exc)], None
    info = {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "pdf": str(find_main_pdf()),
        "sample_pages": SAMPLE_PAGES,
        "context_pages": [p for p in ALL_OCR_PAGES if p not in SAMPLE_PAGES],
        "versions": {
            "rapidocr": getattr(rapidocr, "__version__", None),
            "onnxruntime": ort_ver,
            "pymupdf": getattr(pymupdf, "VersionBind", None) or getattr(pymupdf, "__version__", None),
            "pillow": PIL.__version__,
            "numpy": numpy.__version__,
        },
        "onnx_providers": providers,
    }
    (OUTPUT_DIR / "environment.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def cmd_all(force: bool) -> None:
    t0 = time.perf_counter()
    write_env()
    times = {}
    t = time.perf_counter()
    cmd_extract(force=force)
    times["extract_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    cmd_ocr(force=force)
    times["ocr_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    cmd_parse()
    times["parse_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    cmd_revise()
    times["revise_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    cmd_db()
    times["db_s"] = round(time.perf_counter() - t, 3)
    times["total_s"] = round(time.perf_counter() - t0, 3)
    (OUTPUT_DIR / "run_timing.json").write_text(
        json.dumps(times, indent=2), encoding="utf-8"
    )
    print("timing", times)
    for w in ("cold", "point", "almost", "ally", "fish", "alma mater"):
        print()
        cmd_query(w)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "cmd",
        choices=["extract", "ocr", "parse", "revise", "db", "query", "all", "env"],
    )
    p.add_argument("word", nargs="?")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    if args.cmd == "extract":
        cmd_extract(args.force)
    elif args.cmd == "ocr":
        cmd_ocr(args.force)
    elif args.cmd == "parse":
        cmd_parse()
    elif args.cmd == "revise":
        cmd_revise()
    elif args.cmd == "db":
        cmd_db()
    elif args.cmd == "query":
        if not args.word:
            raise SystemExit("query requires a word")
        cmd_query(args.word)
    elif args.cmd == "env":
        write_env()
        print(OUTPUT_DIR / "environment.json")
    elif args.cmd == "all":
        cmd_all(args.force)


if __name__ == "__main__":
    main()
