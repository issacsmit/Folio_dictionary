from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import numpy as np
from rapidocr import RapidOCR

from .config import ENGINE_NAME, OCR_DIR, OCR_PARAMS, PAGES_DIR, SAMPLE_PAGES, ensure_output_dirs
from .extract import page_image_path
from .layout import detect_layout, load_gray


def ocr_json_path(page: int) -> Path:
    return OCR_DIR / f"page_{page:04d}.json"


def _engine() -> RapidOCR:
    return RapidOCR(params=dict(OCR_PARAMS))


def _to_rgb(gray: np.ndarray) -> np.ndarray:
    return np.stack([gray, gray, gray], axis=-1)


def _boxes_to_lines(result, dx: float, dy: float) -> list[dict]:
    lines = []
    if not result or not result.txts:
        return lines
    for txt, score, box in zip(result.txts, result.scores, result.boxes):
        xs = [float(p[0]) + dx for p in box]
        ys = [float(p[1]) + dy for p in box]
        poly = [[float(p[0]) + dx, float(p[1]) + dy] for p in box]
        lines.append(
            {
                "text": txt,
                "score": float(score),
                "x0": min(xs),
                "y0": min(ys),
                "x1": max(xs),
                "y1": max(ys),
                "poly": poly,
            }
        )
    return lines


def ocr_page(page: int, engine: RapidOCR | None = None, force: bool = False) -> dict:
    ensure_output_dirs()
    out_path = ocr_json_path(page)
    if out_path.exists() and not force:
        data = json.loads(out_path.read_text(encoding="utf-8"))
        if data.get("status") == "ok":
            data["skipped"] = True
            return data
    img_path = page_image_path(page)
    rec = {
        "page": page,
        "image_path": str(img_path),
        "engine": ENGINE_NAME,
        "params": OCR_PARAMS,
        "role": "sample" if page in SAMPLE_PAGES else "context",
        "preprocess": "native 1-bit scan rendered at 600 dpi grayscale; split into two columns; no downscale before engine (Det.limit_side_len=1600/min)",
        "status": "ok",
    }
    if not img_path.exists():
        rec["status"] = "error"
        rec["error"] = f"missing image {img_path}"
        out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return rec
    try:
        t0 = time.perf_counter()
        gray = load_gray(img_path)
        rec["width"] = int(gray.shape[1])
        rec["height"] = int(gray.shape[0])
        rec["image_size"] = [rec["width"], rec["height"]]
        layout = detect_layout(gray)
        rec["layout"] = {
            "header_y": layout.header_y,
            "footer_y": layout.footer_y,
            "left_x": layout.left_x,
            "right_x": layout.right_x,
            "gutter_x": layout.gutter_x,
            "columns": layout.columns,
            "feature_boxes": layout.boxes,
        }
        if engine is None:
            engine = _engine()
        lines = []
        col_meta = []
        for col_i, (x0, y0, x1, y1) in enumerate(layout.columns):
            crop = gray[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            t_col = time.perf_counter()
            result = engine(_to_rgb(crop))
            col_lines = _boxes_to_lines(result, dx=x0, dy=y0)
            for ln in col_lines:
                ln["column"] = col_i
            lines.extend(col_lines)
            col_meta.append(
                {
                    "column": col_i,
                    "crop": [x0, y0, x1, y1],
                    "crop_size": [int(crop.shape[1]), int(crop.shape[0])],
                    "n_lines": len(col_lines),
                    "elapsed_s": round(time.perf_counter() - t_col, 3),
                    "engine_elapse": round(float(getattr(result, "elapse", 0.0) or 0.0), 3),
                }
            )
        lines.sort(key=lambda r: (r.get("column", 0), round(r["y0"] / 6), r["x0"]))
        rec["lines"] = lines
        rec["n_lines"] = len(lines)
        rec["columns"] = col_meta
        rec["elapsed_s"] = round(time.perf_counter() - t0, 3)
        rec["mean_score"] = (
            round(float(np.mean([ln["score"] for ln in lines])), 4) if lines else None
        )
        rec["skipped"] = False
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc()
    out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def ocr_pages(pages: list[int], force: bool = False) -> list[dict]:
    ensure_output_dirs()
    engine = None
    summaries = []
    for i, page in enumerate(pages):
        need = force or not ocr_json_path(page).exists()
        if need and engine is None:
            engine = _engine()
        rec = ocr_page(page, engine=engine, force=force)
        summaries.append(
            {
                "page": page,
                "status": rec.get("status"),
                "n_lines": rec.get("n_lines"),
                "elapsed_s": rec.get("elapsed_s"),
                "skipped": rec.get("skipped", False),
                "error": rec.get("error"),
                "role": rec.get("role"),
            }
        )
        print(
            f"[{i+1}/{len(pages)}] page {page} {rec.get('status')} "
            f"lines={rec.get('n_lines')} t={rec.get('elapsed_s')} skip={rec.get('skipped')}",
            flush=True,
        )
    (OCR_DIR / "ocr_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summaries
