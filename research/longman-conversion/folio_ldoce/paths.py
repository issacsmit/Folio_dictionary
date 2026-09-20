from __future__ import annotations

from pathlib import Path

CONV_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = CONV_ROOT.parent.parent
SOURCE_DIR = WORKSPACE / "电子词典" / "电脑版~朗文当代第六版英汉"
OUTPUT_DIR = CONV_ROOT / "output"
UNPACKED_DIR = OUTPUT_DIR / "unpacked"
PACK_ZIP = OUTPUT_DIR / "longman6-folio-v1.zip"
READMDICT_CACHE = WORKSPACE / "tmp" / "mdx-audit-uv-cache" / "archive-v0"
MDX_PILOT = WORKSPACE / "research" / "mdx-pilot"
