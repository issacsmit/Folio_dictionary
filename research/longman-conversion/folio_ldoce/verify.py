"""Post-conversion checks against required headwords and the pack."""
from __future__ import annotations

import json
from pathlib import Path

from .paths import OUTPUT_DIR, PACK_ZIP, UNPACKED_DIR
from .query import collect_matches, load_pack, query

REQUIRED = [
    "throughout",
    "fish",
    "point",
    "run",
    "cold",
    "light",
    "account",
    "almighty",
    "studies",
    "study",
    "went",
    "indices",
    "propagation",
    "refraction",
    "chatbot",
    "threescore",
]
PHRASES = ["run out of", "take into account"]


def _senses(entry: dict) -> list[dict]:
    out = []

    def walk(items):
        for s in items:
            out.append(s)
            walk(s.get("senses") or [])

    for g in entry.get("pos_groups") or []:
        walk(g.get("senses") or [])
    return out


def verify_pack(pack: Path | None = None) -> dict:
    pack = pack or PACK_ZIP
    root = UNPACKED_DIR if (UNPACKED_DIR / "entries.jsonl").exists() else pack
    manifest, entries, lookup = load_pack(root if root.is_dir() else pack)
    rows = []
    for word in REQUIRED + PHRASES:
        hits = collect_matches(word, lookup)
        rec = {
            "query": word,
            "hit_count": len(hits),
            "matches": [
                {
                    "headword": m.get("headword"),
                    "match": m.get("match"),
                    "kind": (entries.get(m["entry_id"]) or {}).get("kind"),
                    "entry_id": m.get("entry_id"),
                }
                for m in hits[:6]
            ],
            "review": "auto_structure",
        }
        if not hits:
            rec["note"] = "unhit"
            rows.append(rec)
            continue
        primary = entries.get(hits[0]["entry_id"])
        if primary:
            rec["primary_headword"] = primary.get("headword")
            rec["primary_kind"] = primary.get("kind")
            rec["pos"] = [g.get("pos") for g in primary.get("pos_groups") or []]
            rec["ipa"] = [p.get("ipa") for p in primary.get("pronunciations") or []]
            senses = _senses(primary)
            rec["sense_count"] = len(senses)
            rec["sense_preview"] = [
                {
                    "en": (s.get("definition") or {}).get("en"),
                    "zh": (s.get("definition") or {}).get("zh"),
                    "lexunits": s.get("lexunits") or [],
                }
                for s in senses[:6]
            ]
        rows.append(rec)

    checks = {
        "fish_zh_null": None,
        "throughout_two_senses": None,
        "threescore_60": None,
        "propagation_not_verb_defs": None,
        "refraction_not_verb_defs": None,
        "studies_alias": None,
    }
    by = {r["query"]: r for r in rows}
    fish = by.get("fish") or {}
    if fish.get("sense_preview"):
        checks["fish_zh_null"] = all(s.get("zh") is None for s in fish["sense_preview"])
    th = by.get("throughout") or {}
    checks["throughout_two_senses"] = (th.get("sense_count") or 0) >= 2
    ts = by.get("threescore") or {}
    checks["threescore_60"] = any((s.get("en") == "60") for s in ts.get("sense_preview") or [])
    prop = by.get("propagation") or {}
    checks["propagation_not_verb_defs"] = prop.get("primary_kind") == "derived" and prop.get("primary_headword") == "propagation"
    ref = by.get("refraction") or {}
    checks["refraction_not_verb_defs"] = ref.get("primary_kind") == "derived" and ref.get("primary_headword") == "refraction"
    st = by.get("studies") or {}
    checks["studies_alias"] = any(m.get("match") == "alias" and (m.get("headword") or "").lower() == "study" for m in st.get("matches") or [])

    text_dumps = {w: query(w, pack=pack, limit=3) for w in REQUIRED + PHRASES}
    result = {
        "manifest_counts": manifest.get("counts"),
        "required": rows,
        "automatic_checks": checks,
        "automatic_ok": all(v is True for v in checks.values()),
        "query_dumps": text_dumps,
    }
    out = OUTPUT_DIR / "verification.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    matrix = ["# 样本检查矩阵", "", "自动结构校验与代理阅读分开标记。", ""]
    matrix.append("| 查询 | 命中 | 词头 | 类型 | 自动 |")
    matrix.append("| --- | ---: | --- | --- | --- |")
    for row in rows:
        matrix.append(
            f"| {row['query']} | {row['hit_count']} | {row.get('primary_headword') or ''} | {row.get('primary_kind') or row.get('note') or ''} | auto_structure |"
        )
    sample_path = OUTPUT_DIR / "random_sample.json"
    if sample_path.exists():
        matrix.append("\n## 固定种子随机样本（自动结构）\n")
        for row in json.loads(sample_path.read_text(encoding="utf-8")):
            matrix.append(f"- `{row['key']}` status={row['status']} types={row.get('sample_type')} kinds={row.get('kinds')}")
    (OUTPUT_DIR / "sample-matrix.md").write_text("\n".join(matrix), encoding="utf-8")
    return result
