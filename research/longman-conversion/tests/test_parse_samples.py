from __future__ import annotations

import json
from pathlib import Path

from folio_ldoce.normalize import normalize_lookup
from folio_ldoce.parse import parse_html

SAMPLES = Path(__file__).resolve().parents[2] / "mdx-pilot" / "samples.raw.json"


def _samples() -> dict:
    return json.loads(SAMPLES.read_text(encoding="utf-8"))


def _senses(entry: dict) -> list[dict]:
    out = []
    def walk(items):
        for s in items:
            out.append(s)
            walk(s.get("senses") or [])
    for g in entry.get("pos_groups") or []:
        walk(g.get("senses") or [])
    return out


def test_throughout_two_senses_bilingual():
    raw = _samples()["throughout"][0]
    result = parse_html("throughout", raw)
    words = [e for e in result.entries if e["kind"] == "word"]
    assert len(words) == 1
    e = words[0]
    assert e["headword"] == "throughout"
    ipas = [p["ipa"] for p in e["pronunciations"]]
    assert any("θruːˈaʊt" in x for x in ipas)
    pos = e["pos_groups"][0]["pos"]
    assert "preposition" in pos and "adverb" in pos
    senses = _senses(e)
    assert len(senses) == 2
    zh = [s["definition"]["zh"] for s in senses]
    assert any("遍及" in (x or "") for x in zh)
    assert any("自始至终" in (x or "") or "整个期间" in (x or "") for x in zh)
    en = [s["definition"]["en"] for s in senses]
    assert any("every part" in (x or "") for x in en)
    assert any("period" in (x or "") or "beginning" in (x or "") for x in en)


def test_fish_english_only_and_homographs_not_mixed():
    raw = _samples()["fish"][0]
    result = parse_html("fish", raw)
    words = [e for e in result.entries if e["kind"] == "word"]
    assert len(words) == 2
    noun = next(e for e in words if "noun" in e["pos_groups"][0]["pos"])
    verb = next(e for e in words if "verb" in e["pos_groups"][0]["pos"])
    noun_en = " ".join(s["definition"]["en"] or "" for s in _senses(noun))
    verb_en = " ".join(s["definition"]["en"] or "" for s in _senses(verb))
    assert "animal that lives in water" in noun_en
    assert "try to catch fish" in verb_en
    assert "try to catch fish" not in noun_en
    assert "animal that lives in water" not in verb_en
    assert all(s["definition"]["zh"] is None for s in _senses(noun) + _senses(verb))
    assert any(e["kind"] == "phrasal_verb" and "out" in e["headword"] for e in result.entries)


def test_chatbot_english_fallback():
    raw = _samples()["chatbot"][0]
    result = parse_html("chatbot", raw)
    e = result.entries[0]
    sense = _senses(e)[0]
    assert sense["definition"]["zh"] is None
    assert "computer program" in (sense["definition"]["en"] or "")


def test_indices_keeps_crossref_in_definition():
    raw = _samples()["indices"][0]
    result = parse_html("indices", raw)
    e = result.entries[0]
    sense = _senses(e)[0]
    assert "index" in (sense["definition"]["en"] or "")
    assert "复数" in (sense["definition"]["zh"] or "")
    assert any(x["text"].lower() == "index" for x in sense["cross_refs"])


def test_went_is_own_entry():
    raw = _samples()["went"][0]
    result = parse_html("went", raw)
    e = result.entries[0]
    assert e["headword"] == "went"
    assert "past tense" in (_senses(e)[0]["definition"]["en"] or "")


def test_almighty_lexunits_and_us_ipa():
    raw = _samples()["almighty"][0]
    result = parse_html("almighty", raw)
    e = result.entries[0]
    accents = {p["accent"] for p in e["pronunciations"]}
    assert "br" in accents
    senses = _senses(e)
    assert len(senses) == 3
    lex = [lu for s in senses for lu in s.get("lexunits") or []]
    assert any("Almighty" in x for x in lex)


def test_propagation_locator_does_not_expose_verb_defs():
    raw = _samples()["propagation"][0]
    result = parse_html("propagation", raw)
    assert result.record_kind == "converted_derived_locator"
    derived = [e for e in result.entries if e["kind"] == "derived"]
    assert derived and derived[0]["headword"] == "propagation"
    assert derived[0]["parent"]["headword"] == "propagate"
    # lookups from this MDX key must not point at the verb entry
    verb_ids = {e["id"] for e in result.entries if e["kind"] == "word"}
    for hit in result.lookups:
        assert hit.entry_id not in verb_ids
        assert normalize_lookup(hit.headword) == "propagation"


def test_no_placeholder_translation():
    raw = _samples()["fish"][0]
    blob = json.dumps(parse_html("fish", raw).entries, ensure_ascii=False)
    assert "暂无翻译" not in blob
