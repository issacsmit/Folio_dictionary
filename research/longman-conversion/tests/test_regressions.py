from __future__ import annotations

import json
from pathlib import Path

from folio_ldoce.convert import _resolve_link
from folio_ldoce.normalize import phrase_lookup_keys
from folio_ldoce.parse import parse_html
from folio_ldoce.query import rank_matches

SAMPLES = Path(__file__).resolve().parents[2] / "mdx-pilot" / "samples.raw.json"

THREESCORE = """
<link rel="stylesheet" href="ldoce6ec.css"><script src="ldoce6ec.js"></script>
<a name="x_LDOCE6_threescore_1"></a><div>
<a name="x_threescore" id="x_threescore"></a>
<span class="entry"><span class="entryhead"><span class="hwd">threescore</span>
<span class="proncodes"><span class="neutral">/</span><span class="pron">ˈθriːskɔː</span>
<span class="amevarpron"><span class="neutral">$</span> -skɔːr</span><span class="neutral">/</span></span>
<span class="pos">number</span> <span class="registerlab">old use</span>
<span class="buttons"><span class="popup-button">word sets</span>
<div class="at-link"><span class="entry"><span class="popheader popthes">WORD SETS</span>
<span class="wswd">point, <span class="pos">noun</span></span></span></div></span>
</span>
<span class="sense"><span class="def"><en>60</en><tran>六十</tran></span></span>
</span></div>
"""

SCHWA = """
<a name="x_propagate"></a>
<span class="entry"><span class="entryhead"><span class="hwd">propagate</span>
<span class="pos">verb</span></span>
<span class="sense"><span class="def">to spread an idea</span></span>
<span class="runon"><span class="deriv"><span>—</span>propagation</span>
<span class="proncodes"><span class="neutral">/</span><span class="pron">ˌprɒpəˈɡeɪʃ<i>ə</i>n</span>
<span class="amevarpron"><span class="neutral">$</span> ˌprɑː-</span></span>
<span class="pos">noun</span> <span class="gram">[uncountable]</span></span>
</span>
"""

ACCOUNT_VARIANT = """
<a name="x_account_1"></a>
<span class="entry"><span class="entryhead"><span class="hwd">account</span>
<span class="homnum">1</span><span class="pos">noun</span></span>
<span class="sense"><span class="sensenum">1</span>
<span class="lexunit">take account of something</span>
<span class="variant"><span class="linkword">also</span>
<span class="lexvar">take something into account</span></span>
<span class="def"><en>to consider particular facts</en><tran>把某事物考虑进去</tran></span>
</span></span>
"""


def test_threescore_keeps_numeric_english_and_strips_wordsets():
    result = parse_html("threescore", THREESCORE)
    e = result.entries[0]
    assert e["pos_groups"][0]["pos"] == ["number"]
    sense = e["pos_groups"][0]["senses"][0]
    assert sense["definition"]["en"] == "60"
    assert sense["definition"]["zh"] == "六十"
    blob = json.dumps(e, ensure_ascii=False)
    assert "point" not in [p.lower() for g in e["pos_groups"] for p in g["pos"]]


def test_italic_schwa_not_dropped():
    result = parse_html("propagation", SCHWA)
    derived = next(e for e in result.entries if e["kind"] == "derived")
    ipa = " ".join(p["ipa"] for p in derived["pronunciations"])
    assert "ə" in ipa
    assert "ʃən" in ipa.replace(" ", "")


def test_take_into_account_from_lexvar_not_invented():
    result = parse_html("account", ACCOUNT_VARIANT)
    e = result.entries[0]
    sense = e["pos_groups"][0]["senses"][0]
    assert "take something into account" in sense["patterns"]
    norms = {h.norm for h in result.lookups}
    assert "take something into account" in norms
    assert "take into account" in norms
    assert "take account of" in norms


def test_alias_cycle_detected():
    alias = {"a": "b", "b": "a"}
    resolved, err = _resolve_link("a", alias, {}, set(), {})
    assert resolved is None
    assert err.startswith("cycle")


def test_query_ranks_headword_over_collocation():
    ranked = rank_matches(
        "run",
        [
            {"headword": "earth", "match": "collocation", "entry_id": "e"},
            {"headword": "run", "match": "headword", "entry_id": "r"},
        ],
    )
    assert ranked[0]["headword"] == "run"


def test_faq_front_matter_excluded():
    html = '<div class="dict-faq-about"><h2>Vowels</h2><table><tr><td>ɪ</td></tr></table></div>'
    result = parse_html("faq-about", html)
    assert result.record_kind == "excluded_aux"
    assert result.entries == []


def test_phrase_keys_do_not_index_examples():
    keys = phrase_lookup_keys("run out of steam")
    assert "run out of steam" in keys
    assert not any(len(k) > 40 and "freeway" in k for k in keys)


def test_point_noun_verb_not_mixed():
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    result = parse_html("point", samples["point"][0])
    words = [e for e in result.entries if e["kind"] == "word"]
    noun = next(e for e in words if e.get("homograph") == 1 or "noun" in e["pos_groups"][0]["pos"])
    verb = next(e for e in words if e.get("homograph") == 2 or "verb" in e["pos_groups"][0]["pos"])
    noun_en = " ".join(s["definition"]["en"] or "" for g in noun["pos_groups"] for s in g["senses"])
    verb_en = " ".join(s["definition"]["en"] or "" for g in verb["pos_groups"] for s in g["senses"])
    assert "noun" in noun["pos_groups"][0]["pos"]
    assert "verb" in verb["pos_groups"][0]["pos"]
    assert "idea, opinion" in noun_en or "purpose" in noun_en or "sharp" in noun_en
    assert "show somebody something by holding" in verb_en or "finger" in verb_en or "aim" in verb_en
    assert "show somebody something by holding your finger" not in noun_en
