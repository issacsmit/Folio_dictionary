from __future__ import annotations

import json
import time
from pathlib import Path

import pymupdf

from .config import EXTRACT_DPI, PAGES_DIR, ensure_output_dirs, find_main_pdf


def page_image_path(page: int) -> Path:
    return PAGES_DIR / f"page_{page:04d}.png"


def extract_pages(pages: list[int], force: bool = False) -> list[dict]:
    ensure_output_dirs()
    pdf_path = find_main_pdf()
    records = []
    doc = pymupdf.open(pdf_path)
    try:
        n_pages = doc.page_count
        for page_no in pages:
            rec = {
                "page": page_no,
                "pdf": str(pdf_path),
                "pdf_pages": n_pages,
                "path": str(page_image_path(page_no)),
                "status": "ok",
            }
            out = page_image_path(page_no)
            if out.exists() and not force:
                rec["skipped"] = True
                rec["bytes"] = out.stat().st_size
                records.append(rec)
                continue
            if page_no < 1 or page_no > n_pages:
                rec["status"] = "error"
                rec["error"] = f"page {page_no} out of range 1..{n_pages}"
                records.append(rec)
                continue
            t0 = time.perf_counter()
            page = doc[page_no - 1]
            images = page.get_images(full=True)
            rec["embedded"] = [
                {
                    "xref": im[0],
                    "width": im[2],
                    "height": im[3],
                    "bpc": im[4],
                    "cs": im[5],
                    "filter": im[8] if len(im) > 8 else None,
                }
                for im in images
            ]
            pix = page.get_pixmap(dpi=EXTRACT_DPI, colorspace=pymupdf.csGRAY)
            pix.save(str(out))
            rec["width"] = pix.width
            rec["height"] = pix.height
            rec["n"] = pix.n
            rec["bytes"] = out.stat().st_size
            rec["elapsed_s"] = round(time.perf_counter() - t0, 3)
            rec["method"] = f"pymupdf.get_pixmap(dpi={EXTRACT_DPI}, csGRAY)"
            rec["skipped"] = False
            records.append(rec)
    finally:
        doc.close()
    manifest = PAGES_DIR / "extract_manifest.json"
    old = []
    if manifest.exists():
        old = json.loads(manifest.read_text(encoding="utf-8"))
    by_page = {r["page"]: r for r in old if "page" in r}
    for r in records:
        by_page[r["page"]] = r
    merged = [by_page[k] for k in sorted(by_page)]
    manifest.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return records
