from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import OUTPUT_DIR
from .normalize import headword_key, phrase_key


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    db_path = db_path or (OUTPUT_DIR / "folio_sample.sqlite")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def lookup(word: str, db_path: Path | None = None) -> dict:
    q = (word or "").strip()
    keys = []
    for fn in (headword_key, phrase_key, str.lower):
        k = fn(q)
        if k and k not in keys:
            keys.append(k)
    keys.append(q.lower())
    con = connect(db_path)
    try:
        entry_ids = []
        seen = set()
        for k in keys:
            rows = con.execute(
                "SELECT entry_id, kind FROM lookup WHERE qkey = ?", (k,)
            ).fetchall()
            for r in rows:
                if r["entry_id"] not in seen:
                    seen.add(r["entry_id"])
                    entry_ids.append((r["entry_id"], r["kind"], k))
        entries = []
        for eid, kind, matched in entry_ids:
            e = con.execute("SELECT * FROM entries WHERE id = ?", (eid,)).fetchone()
            if not e:
                continue
            senses = [
                dict(s)
                for s in con.execute(
                    "SELECT sense_no, labels_json, definition_en, definition_zh FROM senses WHERE entry_id = ? ORDER BY id",
                    (eid,),
                )
            ]
            for s in senses:
                s["labels"] = json.loads(s.pop("labels_json") or "[]")
            colos = [
                dict(c)
                for c in con.execute(
                    "SELECT sense_no, phrase_display, phrase_key, explanation_zh, source FROM collocations WHERE entry_id = ? ORDER BY id",
                    (eid,),
                )
            ]
            entries.append(
                {
                    "matched_as": kind,
                    "matched_key": matched,
                    "id": e["id"],
                    "headword_display": e["headword_display"],
                    "headword_key": e["headword_key"],
                    "homograph": e["homograph"],
                    "pos": e["pos"],
                    "ipa_raw": e["ipa_raw"],
                    "ipa_br": e["ipa_br"],
                    "ipa_am": e["ipa_am"],
                    "ipa_uncertain": bool(e["ipa_uncertain"]),
                    "complete": bool(e["complete"]),
                    "page_start": e["page_start"],
                    "page_end": e["page_end"],
                    "revised": bool(e["revised"]),
                    "senses": senses,
                    "collocations": colos,
                }
            )
        return {"query": word, "keys_tried": keys, "n": len(entries), "entries": entries}
    finally:
        con.close()


def format_lookup(result: dict) -> str:
    lines = [f"query: {result['query']}  hits: {result['n']}"]
    if not result["entries"]:
        lines.append("(no exact hit in sample DB)")
        return "\n".join(lines)
    for e in result["entries"]:
        ipa = e.get("ipa_raw") or ""
        flag = "  [ipa uncertain]" if e.get("ipa_uncertain") else ""
        lines.append(
            f"- {e['headword_display']}  {e.get('pos') or ''}  /{ipa}/{flag}  "
            f"p.{e['page_start']}-{e['page_end']}  complete={e['complete']} revised={e['revised']}"
        )
        for s in e["senses"]:
            zh = s.get("definition_zh") or "—"
            labs = " ".join(s.get("labels") or [])
            lines.append(f"    {s.get('sense_no')}. {labs} {zh}")
        for c in e["collocations"][:12]:
            lines.append(
                f"    · {c.get('phrase_display')}  {c.get('explanation_zh') or ''}"
            )
    return "\n".join(lines)
