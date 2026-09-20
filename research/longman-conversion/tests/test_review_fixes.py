"""Regressions for the 2026-09-20 conversion review."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from folio_ldoce.parse import parse_html
from folio_ldoce.query import collect_matches
from folio_ldoce import validate as validate_mod
from folio_ldoce.validate import validate_zip

STUDY_SENSE3 = """
<a name="x_study_1"></a>
<span class="entry"><span class="entryhead"><span class="hwd">study</span>
<span class="homnum">1</span><span class="pos">noun</span></span>
<span class="sense newline"><span class="sensenum">3</span>
<span class="signpost"><SIGNEN>subject</SIGNEN><SIGN>学科</SIGN></span>
<span class="gram">[uncountable]</span>
<span class="variant"><span class="linkword">also</span> <span class="lexvar">studies</span></span>
<span class="subsense"><span class="def"><en>a subject that people study at a college or university</en><tran>〔大学里的〕学科﹔学业</tran></span></span>
<span class="def"><span class="gramexa"><span class="propformprep">study of</span>
<span class="example">Linguistics is the study of language.</span></span>
<span class="example">Environmental Studies</span>
<span class="colloexa"><span class="collo">literary/historical/scientific etc study</span>
<span class="example">the scientific study of earthquakes</span></span>
</span></span>
</span>
"""

U_ABBR = """
<a name="x_Udot"></a>
<span class="entry"><span class="entryhead"><span class="hwd">U.</span>
<span class="pos">noun</span></span>
<span class="sense"><span class="geo">American English</span>
<span class="registerlab">informal</span>
<span class="def"><en>an abbreviation of</en><tran>大学</tran></span>
<span class="fullform">university</span>
</span></span>
"""

V_ABBR = """
<a name="x_vdot"></a>
<span class="entry"><span class="entryhead"><span class="hwd">v.</span></span>
<span class="sense"><span class="sensenum">1</span>
<span class="def"><en>a written abbreviation of</en><tran>动词</tran></span>
<span class="fullform">verb</span></span>
<span class="sense"><span class="sensenum">2</span>
<span class="geo">British English</span>
<span class="def"><en>the written abbreviation of</en><tran>很﹐非常</tran></span>
<span class="fullform">very</span></span>
<span class="sense"><span class="sensenum">3</span>
<span class="def"><en>a written abbreviation of <span class="fullform">versus</span>, used in legal trials</en><tran>对﹐诉</tran></span>
</span></span>
"""

U_LETTER = """
<a name="x_U"></a>
<span class="entry"><span class="entryhead"><span class="hwd">U</span>
<span class="pos">noun</span></span>
<span class="sense"><span class="def"><en>the 21st letter of the English alphabet</en><tran>英语字母表的第二十一个字母</tran></span></span>
</span>
"""


def _senses(entry):
    out = []

    def walk(items):
        for s in items:
            out.append(s)
            walk(s.get("senses") or [])

    for g in entry.get("pos_groups") or []:
        walk(g.get("senses") or [])
    return out


def test_study_parent_def_is_not_collocation_shell():
    result = parse_html("study", STUDY_SENSE3)
    e = result.entries[0]
    parent = e["pos_groups"][0]["senses"][0]
    blob = json.dumps(parent, ensure_ascii=False)
    assert "study ofliterary" not in blob
    assert "literary/historical/scientific etc study" not in (parent["definition"]["en"] or "")
    assert parent["definition"]["en"] is None
    assert parent["definition"]["zh"] is None
    subs = parent["senses"]
    assert subs
    assert "college or university" in (subs[0]["definition"]["en"] or "")
    assert "学科" in (subs[0]["definition"]["zh"] or "")
    assert any("study of" == p or p.startswith("study of") for p in parent["patterns"])


def test_abbreviation_fullform_appended_not_duplicated():
    u = parse_html("U.", U_ABBR).entries[0]
    sense = _senses(u)[0]
    assert sense["definition"]["en"] == "an abbreviation of university"
    assert sense["definition"]["zh"] == "大学"

    v = parse_html("v.", V_ABBR).entries[0]
    senses = _senses(v)
    assert senses[0]["definition"]["en"] == "a written abbreviation of verb"
    assert senses[1]["definition"]["en"] == "the written abbreviation of very"
    assert "versus" in (senses[2]["definition"]["en"] or "")
    assert senses[2]["definition"]["en"].count("versus") == 1


def test_period_keys_kept_and_query_prefers_exact():
    u_dot = parse_html("U.", U_ABBR)
    u_let = parse_html("U", U_LETTER)
    norms_dot = {h.norm for h in u_dot.lookups}
    norms_let = {h.norm for h in u_let.lookups}
    assert "u." in norms_dot
    assert "u" in norms_dot
    assert "u" in norms_let
    lookup = {
        "u.": [{"headword": "U.", "match": "headword", "entry_id": "abbr", "key_raw": "U.", "sense_id": None}],
        "u": [
            {"headword": "U", "match": "headword", "entry_id": "letter", "key_raw": "U", "sense_id": None},
            {"headword": "U.", "match": "headword", "entry_id": "abbr", "key_raw": "U.", "sense_id": None},
        ],
        "v.": [{"headword": "v.", "match": "headword", "entry_id": "vabbr", "key_raw": "v.", "sense_id": None}],
        "v": [
            {"headword": "V", "match": "headword", "entry_id": "vletter", "key_raw": "V", "sense_id": None},
            {"headword": "v.", "match": "headword", "entry_id": "vabbr", "key_raw": "v.", "sense_id": None},
        ],
        "run": [{"headword": "run", "match": "headword", "entry_id": "run", "key_raw": "run", "sense_id": None}],
    }
    assert collect_matches("U.", lookup)[0]["entry_id"] == "abbr"
    assert collect_matches("U", lookup)[0]["entry_id"] == "letter"
    assert collect_matches("v.", lookup)[0]["entry_id"] == "vabbr"
    assert collect_matches("V", lookup)[0]["entry_id"] == "vletter"
    assert collect_matches("run.", lookup)[0]["entry_id"] == "run"
    assert collect_matches("Run", lookup)[0]["entry_id"] == "run"


def _mini_entry(eid="e1", headword="cat", sense_id="e1#s1", parent=None):
    return {
        "id": eid,
        "kind": "word",
        "headword": headword,
        "display": headword,
        "homograph": None,
        "source": {"mdx_keys": [headword], "anchor": eid},
        "pronunciations": [],
        "frequency": None,
        "inflections": [],
        "pos_groups": [
            {
                "pos": ["noun"],
                "grammar": [],
                "labels": [],
                "senses": [
                    {
                        "id": sense_id,
                        "number": "1",
                        "signpost": None,
                        "grammar": [],
                        "labels": [],
                        "patterns": [],
                        "lexunits": [],
                        "definition": {"en": "an animal", "zh": "猫"},
                        "cross_refs": [],
                        "phrases": [],
                        "senses": [],
                    }
                ],
            }
        ],
        "phrases": [],
        "cross_refs": [],
        "parent": parent,
        "notes": [],
    }


def _write_zip(path: Path, entries: list[dict], lookups: list[dict], tamper_entries: bool = False) -> Path:
    entries_b = ("\n".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in entries) + "\n").encode("utf-8")
    lookup_b = ("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in lookups) + "\n").encode("utf-8")
    if tamper_entries:
        hashed = entries_b
        entries_b = entries_b + b" "
    else:
        hashed = entries_b
    manifest = {
        "format": "folio-dict-pack",
        "format_version": "1.0",
        "pack_id": "test",
        "parser_version": "1.1.0",
        "source": {"name": "t", "mdx_path": "t.mdx", "mdx_sha256": "a" * 64, "mdx_bytes": 1},
        "languages": {"headword": "en", "definition": ["en", "zh"]},
        "files": ["manifest.json", "entries.jsonl", "lookup.jsonl"],
        "counts": {"entries": len(entries), "lookup_keys": len(lookups)},
        "checksums": {
            "entries.jsonl": hashlib.sha256(hashed).hexdigest(),
            "lookup.jsonl": hashlib.sha256(lookup_b).hexdigest(),
        },
    }
    man_b = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", man_b)
        zf.writestr("entries.jsonl", entries_b)
        zf.writestr("lookup.jsonl", lookup_b)
    return path


def test_validate_zip_reads_zip_not_unpacked(tmp_path, monkeypatch):
    bad = tmp_path / "unpacked"
    bad.mkdir()
    (bad / "manifest.json").write_text("{}", encoding="utf-8")
    (bad / "entries.jsonl").write_text("{}\n", encoding="utf-8")
    (bad / "lookup.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(validate_mod, "OUTPUT_DIR", bad, raising=False)
    entry = _mini_entry()
    lookups = [
        {
            "norm": "cat",
            "matches": [
                {
                    "entry_id": "e1",
                    "sense_id": "e1#s1",
                    "match": "headword",
                    "headword": "cat",
                    "key_raw": "cat",
                }
            ],
        }
    ]
    zpath = _write_zip(tmp_path / "good.zip", [entry], lookups)
    result = validate_zip(zpath)
    assert result["ok"], result["errors"]
    assert result["entries"] == 1


def test_validate_zip_detects_checksum_tamper(tmp_path):
    entry = _mini_entry()
    lookups = [
        {
            "norm": "cat",
            "matches": [
                {
                    "entry_id": "e1",
                    "sense_id": "e1#s1",
                    "match": "headword",
                    "headword": "cat",
                    "key_raw": "cat",
                }
            ],
        }
    ]
    zpath = _write_zip(tmp_path / "bad.zip", [entry], lookups, tamper_entries=True)
    result = validate_zip(zpath)
    assert not result["ok"]
    assert any("checksum mismatch" in e for e in result["errors"])


def test_validate_zip_detects_bad_sense_and_parent(tmp_path):
    entry = _mini_entry(parent={"id": "missing", "headword": "x", "relation": "runon"})
    lookups = [
        {
            "norm": "cat",
            "matches": [
                {
                    "entry_id": "e1",
                    "sense_id": "no-such-sense",
                    "match": "phrase",
                    "headword": "cat",
                    "key_raw": "cat",
                }
            ],
        }
    ]
    zpath = _write_zip(tmp_path / "refs.zip", [entry], lookups)
    result = validate_zip(zpath)
    assert not result["ok"]
    assert any("sense" in e for e in result["errors"])
    assert any("parent.id" in e for e in result["errors"])
