from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import OUTPUT_DIR, ensure_output_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
  id TEXT PRIMARY KEY,
  headword_display TEXT NOT NULL,
  headword_key TEXT NOT NULL,
  homograph INTEGER,
  pos TEXT,
  ipa_raw TEXT,
  ipa_br TEXT,
  ipa_am TEXT,
  ipa_uncertain INTEGER NOT NULL DEFAULT 1,
  complete INTEGER NOT NULL,
  incomplete_reason TEXT,
  page_start INTEGER,
  page_end INTEGER,
  column_start INTEGER,
  bbox_json TEXT,
  raw_ocr TEXT,
  revised INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_entries_key ON entries(headword_key);
CREATE INDEX IF NOT EXISTS idx_entries_display ON entries(headword_display);

CREATE TABLE IF NOT EXISTS senses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_id TEXT NOT NULL,
  sense_no TEXT,
  labels_json TEXT,
  definition_en TEXT,
  definition_zh TEXT,
  FOREIGN KEY(entry_id) REFERENCES entries(id)
);
CREATE INDEX IF NOT EXISTS idx_senses_entry ON senses(entry_id);

CREATE TABLE IF NOT EXISTS collocations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_id TEXT NOT NULL,
  sense_no TEXT,
  phrase_display TEXT NOT NULL,
  phrase_key TEXT NOT NULL,
  explanation_zh TEXT,
  labels_json TEXT,
  source TEXT,
  FOREIGN KEY(entry_id) REFERENCES entries(id)
);
CREATE INDEX IF NOT EXISTS idx_colo_entry ON collocations(entry_id);
CREATE INDEX IF NOT EXISTS idx_colo_key ON collocations(phrase_key);

CREATE TABLE IF NOT EXISTS lookup (
  qkey TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  PRIMARY KEY (qkey, entry_id, kind)
);
CREATE INDEX IF NOT EXISTS idx_lookup_qkey ON lookup(qkey);
"""


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_db(auto_path: Path | None = None, revised_path: Path | None = None) -> Path:
    ensure_output_dirs()
    auto_path = auto_path or (OUTPUT_DIR / "entries.auto.jsonl")
    revised_path = revised_path or (OUTPUT_DIR / "entries.revised.jsonl")
    db_path = OUTPUT_DIR / "folio_sample.sqlite"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        auto = _load_jsonl(auto_path)
        revised = {e["id"]: e for e in _load_jsonl(revised_path)}
        # product query uses revised overlay when present, but keep auto rows
        by_id = {e["id"]: e for e in auto}
        for eid, e in revised.items():
            merged = dict(by_id.get(eid, {}))
            merged.update(e)
            merged["revised"] = 1
            by_id[eid] = merged
            if eid not in {x["id"] for x in auto}:
                by_id[eid] = merged
        cur = con.cursor()
        for e in by_id.values():
            cur.execute(
                """
                INSERT INTO entries(
                  id, headword_display, headword_key, homograph, pos,
                  ipa_raw, ipa_br, ipa_am, ipa_uncertain, complete,
                  incomplete_reason, page_start, page_end, column_start,
                  bbox_json, raw_ocr, revised
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    e.get("id"),
                    e.get("headword_display") or "",
                    e.get("headword_key") or "",
                    e.get("homograph"),
                    e.get("pos"),
                    e.get("ipa_raw"),
                    e.get("ipa_br"),
                    e.get("ipa_am"),
                    1 if e.get("ipa_uncertain", True) else 0,
                    1 if e.get("complete") else 0,
                    e.get("incomplete_reason"),
                    e.get("page_start"),
                    e.get("page_end"),
                    e.get("column_start"),
                    json.dumps(e.get("bbox"), ensure_ascii=False) if e.get("bbox") else None,
                    e.get("raw_ocr"),
                    1 if e.get("revised") else 0,
                ),
            )
            for s in e.get("senses") or []:
                cur.execute(
                    """
                    INSERT INTO senses(entry_id, sense_no, labels_json, definition_en, definition_zh)
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        e.get("id"),
                        s.get("sense_no"),
                        json.dumps(s.get("labels") or [], ensure_ascii=False),
                        s.get("definition_en"),
                        s.get("definition_zh"),
                    ),
                )
            for c in e.get("collocations") or []:
                cur.execute(
                    """
                    INSERT INTO collocations(
                      entry_id, sense_no, phrase_display, phrase_key,
                      explanation_zh, labels_json, source
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        e.get("id"),
                        c.get("sense_no"),
                        c.get("phrase_display") or "",
                        c.get("phrase_key") or "",
                        c.get("explanation_zh"),
                        json.dumps(c.get("labels") or [], ensure_ascii=False),
                        c.get("source"),
                    ),
                )
            keys = {e.get("headword_key") or ""}
            disp = (e.get("headword_display") or "").lower()
            keys.add(disp)
            for k in list(keys):
                if k:
                    cur.execute(
                        "INSERT OR IGNORE INTO lookup(qkey, entry_id, kind) VALUES (?,?,?)",
                        (k, e["id"], "headword"),
                    )
            for c in e.get("collocations") or []:
                pk = c.get("phrase_key")
                if pk:
                    cur.execute(
                        "INSERT OR IGNORE INTO lookup(qkey, entry_id, kind) VALUES (?,?,?)",
                        (pk, e["id"], "collocation"),
                    )
        con.commit()
    finally:
        con.close()
    return db_path
