from __future__ import annotations

from pathlib import Path

PILOT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PILOT_ROOT.parents[1]
OUTPUT_DIR = PILOT_ROOT / "output"
PAGES_DIR = OUTPUT_DIR / "pages"
OCR_DIR = OUTPUT_DIR / "ocr"
LAYOUT_DIR = OUTPUT_DIR / "layout"
LOG_DIR = OUTPUT_DIR / "logs"

SAMPLE_PAGES = (
    list(range(99, 105))
    + list(range(499, 505))
    + list(range(999, 1005))
    + list(range(1999, 2005))
)
CONTEXT_PAGES = [98, 105, 498, 505, 998, 1005, 1998, 2005]
ALL_OCR_PAGES = sorted(set(SAMPLE_PAGES + CONTEXT_PAGES))

MAIN_PDF_MARKERS = ("英英", "双解")

OCR_PARAMS = {
    "Global.use_cls": False,
    "Global.max_side_len": 8000,
    "Global.log_level": "warning",
    "EngineConfig.onnxruntime.use_dml": True,
    "Det.limit_side_len": 1600,
    "Det.limit_type": "min",
    "Det.max_candidates": 4000,
    "Det.thresh": 0.3,
    "Det.box_thresh": 0.4,
}

ENGINE_NAME = "rapidocr+PP-OCRv6-small+onnxruntime-directml"
EXTRACT_DPI = 600

FEATURE_TITLE_RE = (
    r"^(THESAURUS|GRAMMAR|COLLOCATIONS|REGISTER|USAGE|WORD\s+CHOICE|"
    r"WORD\s+FOCUS|PRAGMATICS|SPOKEN\s+PHRASES|PHRASES|FREQUENCY|"
    r"词语搭配|词语辨析|语法)"
)

POS_TOKENS = (
    "linking verb",
    "modal verb",
    "auxiliary",
    "predeterminer",
    "determiner",
    "exclamation",
    "interjection",
    "abbreviation",
    "prefix",
    "suffix",
    "number",
    "pron",
    "prep",
    "conj",
    "det",
    "adj",
    "adv",
    "n",
    "v",
)


def find_main_pdf() -> Path:
    folder = PROJECT_ROOT / "电子词典"
    if not folder.is_dir():
        raise FileNotFoundError(f"dictionary folder missing: {folder}")
    matches = [
        p
        for p in folder.glob("*.pdf")
        if all(m in p.name for m in MAIN_PDF_MARKERS)
    ]
    if not matches:
        raise FileNotFoundError(f"main Longman bilingual PDF not found in {folder}")
    if len(matches) > 1:
        matches.sort(key=lambda p: p.stat().st_size, reverse=True)
    return matches[0]


def ensure_output_dirs() -> None:
    for d in (OUTPUT_DIR, PAGES_DIR, OCR_DIR, LAYOUT_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
