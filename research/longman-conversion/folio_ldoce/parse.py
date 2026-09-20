"""Parse one Longman LDOCE6 bilingual HTML record into Folio entries."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from lxml import html as lhtml
from lxml.html import HtmlElement

from .normalize import collapse_ws, empty_to_none, lookup_keys_for, normalize_lookup, phrase_lookup_keys, strip_leading_dash

DROP_TAGS = {"script", "link", "style", "noscript"}
DROP_CLASSES = {
    "at-link",
    "popup-button",
    "verbtable",
    "etymology",
    "etymbox",
    "thesbox",
    "usagebox",
    "grambox",
    "f2nbox",
    "popwf",
    "wf",
    "entrymenu",
    "pope_menu",
    "errorbox",
    "imgholder",
    "popexa",
    "popthes",
    "popcollo",
    "popetym",
    "popphrase",
    "pope_menu",
}
SENSE_SKIP_ANCESTORS = {
    "phrvbentry",
    "phrvbs",
    "runon",
    "collobox",
    "thesbox",
    "usagebox",
    "grambox",
    "f2nbox",
    "exponent",
    "at-link",
    "popwf",
    "wf",
    "example",
    "exas",
    "verbtable",
    "etymology",
    "menuitem",
}
DEF_SKIP_CLASSES = {
    "example",
    "exas",
    "exaen",
    "colloinexa",
    "gramexa",
    "colloexa",
    "collo",
    "propform",
    "propformprep",
    "cllt",
    "cl",
}
_ABBR_OF_RE = re.compile(r"(?:written\s+)?abbreviation\s+of\.?$", re.I)
_LEXICAL_RE = re.compile(r"[A-Za-z0-9\u00c0-\u024f\u4e00-\u9fff]")
CUTOFF_CLASSES = {"sense", "phrvbs", "phrvbentry", "runon", "tail", "spokensect", "collobox"}

_CLASS_RE_CACHE: dict[str, str] = {}


def _has(el: HtmlElement | None, name: str) -> bool:
    if el is None:
        return False
    return name in (el.get("class") or "").split()


def _classes(el: HtmlElement) -> set[str]:
    return set((el.get("class") or "").split())


def _xpath_class(name: str) -> str:
    expr = _CLASS_RE_CACHE.get(name)
    if expr is None:
        expr = f'.//*[contains(concat(" ", normalize-space(@class), " "), " {name} ")]'
        _CLASS_RE_CACHE[name] = expr
    return expr


def _drop(el: HtmlElement) -> None:
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def _ancestors(el: HtmlElement, stop: HtmlElement | None = None) -> Iterable[HtmlElement]:
    cur = el.getparent()
    while cur is not None and cur is not stop:
        yield cur
        cur = cur.getparent()


def _ancestor_has(el: HtmlElement, names: set[str], stop: HtmlElement | None = None) -> bool:
    return any(_classes(a) & names for a in _ancestors(el, stop=stop))


def _iter_text(el: HtmlElement, skip_classes: set[str] | None = None) -> Iterable[str]:
    skip_classes = skip_classes or set()
    if el.tag in DROP_TAGS or el.tag in {"img"}:
        return
    if _classes(el) & skip_classes:
        return
    if el.text:
        yield el.text
    for child in el:
        if isinstance(child, HtmlElement):
            yield from _iter_text(child, skip_classes)
            if child.tail:
                yield child.tail


def _text(el: HtmlElement | None, skip_classes: set[str] | None = None) -> str:
    if el is None:
        return ""
    return collapse_ws("".join(_iter_text(el, skip_classes)))


def _ipa_text(el: HtmlElement | None) -> str:
    """Keep IPA characters glued across <i> etc.; collapse only whitespace."""
    return _text(el)


def _first(el: HtmlElement, class_name: str) -> HtmlElement | None:
    found = el.xpath(_xpath_class(class_name))
    return found[0] if found else None


def _clean_root(raw_html: str) -> HtmlElement:
    root = lhtml.fromstring(raw_html)
    for el in list(root.xpath("//script|//link|//style|//noscript")):
        _drop(el)
    for el in list(root.xpath("//*[@class]")):
        if _classes(el) & DROP_CLASSES:
            _drop(el)
    return root


def _split_pos(raw: str) -> list[str]:
    parts = []
    for chunk in re.split(r"[,/]|，", raw):
        item = collapse_ws(chunk).strip(" .;")
        if item:
            parts.append(item)
    return parts


def _split_grammar(raw: str) -> list[str]:
    text = collapse_ws(raw).strip("[]")
    if not text:
        return []
    return [collapse_ws(p).strip("[] ") for p in re.split(r"[,;]", text) if collapse_ws(p).strip("[] ")]


def _label_type(value: str, class_name: str) -> str:
    if class_name == "geo":
        return "geo"
    if class_name in {"registerlab", "register"}:
        return "register"
    if class_name == "ac":
        return "domain"
    low = value.casefold()
    if any(x in low for x in ("american", "british", "australian", "english")):
        return "geo"
    if any(x in low for x in ("formal", "informal", "spoken", "literary", "old", "slang", "taboo", "humorous")):
        return "register"
    return "other"


def _labels_in(el: HtmlElement, scope: str, stop: HtmlElement | None = None) -> list[dict]:
    out = []
    seen = set()
    for class_name in ("registerlab", "geo", "ac"):
        for node in el.xpath(_xpath_class(class_name)):
            if stop is not None and _ancestor_has(node, CUTOFF_CLASSES, stop=stop):
                continue
            if _ancestor_has(node, DEF_SKIP_CLASSES | {"collobox", "phrvbentry", "runon"}, stop=el):
                continue
            value = _text(node)
            if not value:
                continue
            key = (class_name, value, scope)
            if key in seen:
                continue
            seen.add(key)
            out.append({"type": _label_type(value, class_name), "value": value, "scope": scope})
    return out


def _bilingual_pair(el: HtmlElement, en_tags: tuple[str, ...], zh_tags: tuple[str, ...]) -> dict:
    en = None
    zh = None
    for child in el.iter():
        if not isinstance(child, HtmlElement):
            continue
        tag = child.tag.lower() if isinstance(child.tag, str) else ""
        if tag in en_tags and en is None:
            en = empty_to_none(_text(child, DEF_SKIP_CLASSES))
        elif tag in zh_tags and zh is None:
            zh = empty_to_none(_text(child, DEF_SKIP_CLASSES))
    return {"en": en, "zh": zh}


def _lexical(text: str | None) -> str | None:
    text = empty_to_none(text)
    if not text or not _LEXICAL_RE.search(text):
        return None
    return text


def extract_definition(def_el: HtmlElement) -> dict:
    """Return en/zh only for real glosses, not grammar/collocation shells."""
    pair = _bilingual_pair(def_el, ("en",), ("tran",))
    pair["en"] = _lexical(pair["en"])
    pair["zh"] = _lexical(pair["zh"])
    if pair["en"] is None and pair["zh"] is None:
        pair["en"] = _lexical(_text(def_el, DEF_SKIP_CLASSES))
    return pair


def _iter_class(el: HtmlElement, name: str) -> Iterable[HtmlElement]:
    if _has(el, name):
        yield el
    yield from el.xpath(_xpath_class(name))


def _pronunciations(region: HtmlElement) -> list[dict]:
    out = []
    seen_nodes = set()
    for codes in _iter_class(region, "proncodes"):
        if id(codes) in seen_nodes:
            continue
        seen_nodes.add(id(codes))
        br_nodes = []
        for n in _iter_class(codes, "pron"):
            if _ancestor_has(n, {"amevarpron"}, stop=codes):
                continue
            br_nodes.append(n)
        am_nodes = list(_iter_class(codes, "amevarpron")) + list(_iter_class(codes, "amepron"))
        br = empty_to_none(_ipa_text(br_nodes[0])) if br_nodes else None
        am = empty_to_none(_ipa_text(am_nodes[0])) if am_nodes else None
        if am:
            am = re.sub(r"^\$\s*", "", am).strip()
        raw = _text(codes)
        if br:
            out.append({"ipa": br, "accent": "br", "raw": raw})
        if am:
            out.append({"ipa": am, "accent": "us", "raw": raw})
        if not br and not am:
            ipa = empty_to_none(re.sub(r"[/]", " ", raw))
            ipa = empty_to_none(ipa.replace("$", " "))
            if ipa:
                out.append({"ipa": ipa, "accent": "unspecified", "raw": raw})
    seen = set()
    uniq = []
    for item in out:
        key = (item["ipa"], item["accent"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq


def _cross_refs(el: HtmlElement, stop: HtmlElement | None = None) -> list[dict]:
    out = []
    seen = set()
    for node in el.xpath(_xpath_class("refhwd")) + el.xpath(_xpath_class("reflex")):
        if _ancestor_has(node, DEF_SKIP_CLASSES | DROP_CLASSES, stop=el):
            continue
        text = _text(node)
        if text.casefold().startswith("at "):
            text = text[3:].strip()
        if not text:
            continue
        href = None
        homograph = None
        sense = None
        cur = node
        while cur is not None and cur is not stop:
            if cur.tag == "a" and cur.get("href"):
                href = cur.get("href")
                break
            cur = cur.getparent()
        hom_nodes = node.xpath("./following-sibling::*[contains(concat(' ', normalize-space(@class), ' '), ' refhomnum ')]")
        sense_nodes = node.xpath("./following-sibling::*[contains(concat(' ', normalize-space(@class), ' '), ' refsensenum ')]")
        search_root = node.getparent() if node.getparent() is not None else el
        for sibling in list(search_root):
            if _has(sibling, "refhomnum"):
                hom_nodes.append(sibling)
            if _has(sibling, "refsensenum"):
                sense_nodes.append(sibling)
        if hom_nodes:
            try:
                homograph = int(re.sub(r"\D", "", _text(hom_nodes[0])) or "0") or None
            except ValueError:
                homograph = None
        if sense_nodes:
            sense = empty_to_none(_text(sense_nodes[0]).strip("()"))
        key = (text, href, homograph, sense)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "text": text,
                "href": href,
                "homograph": homograph,
                "sense": sense,
                "relation": "see",
            }
        )
    return out


def _anchor_before(el: HtmlElement) -> str | None:
    prev = el.getprevious()
    while prev is not None:
        if prev.tag == "a" and (prev.get("id") or prev.get("name")):
            return prev.get("id") or prev.get("name")
        if prev.tag == "a" or (isinstance(prev, HtmlElement) and not _classes(prev)):
            prev = prev.getprevious()
            continue
        break
    # descendant leading anchor
    for child in el:
        if child.tag == "a" and (child.get("id") or child.get("name")):
            return child.get("id") or child.get("name")
        break
    return None


def _head_region_nodes(entry: HtmlElement) -> list[HtmlElement]:
    nodes = []
    for el in entry.iter():
        if el is entry:
            continue
        if not isinstance(el, HtmlElement):
            continue
        if _classes(el) & CUTOFF_CLASSES:
            break
        nodes.append(el)
    return nodes


def _in_head(el: HtmlElement, head_ids: set[int]) -> bool:
    return id(el) in head_ids


def _headword(entry: HtmlElement, head_ids: set[int]) -> str:
    for node in entry.xpath(_xpath_class("hwd")):
        if id(node) in head_ids or not _ancestor_has(node, {"phrvbentry", "runon"}, stop=entry):
            text = _text(node)
            if text:
                return text
    hyp = _first(entry, "hyphenation")
    return _text(hyp) if hyp is not None else ""


def _homograph(head_nodes: list[HtmlElement]) -> int | None:
    for node in head_nodes:
        if _has(node, "homnum"):
            digits = re.sub(r"\D", "", _text(node))
            if digits:
                try:
                    return int(digits)
                except ValueError:
                    return None
    return None


def _head_pos(head_nodes: list[HtmlElement]) -> list[str]:
    poses: list[str] = []
    for node in head_nodes:
        if _has(node, "pos") and not _ancestor_has(node, {"wswd", "wf", "group"}):
            poses.extend(_split_pos(_text(node)))
    # unique stable
    out = []
    for p in poses:
        if p not in out:
            out.append(p)
    return out


def _head_grammar(head_nodes: list[HtmlElement]) -> list[str]:
    grams: list[str] = []
    for node in head_nodes:
        if _has(node, "gram"):
            grams.extend(_split_grammar(_text(node)))
    out = []
    for g in grams:
        if g not in out:
            out.append(g)
    return out


def _frequency(head_nodes: list[HtmlElement]) -> dict | None:
    stars = spoken = written = None
    for node in head_nodes:
        if _has(node, "level"):
            stars = _text(node) or stars
        if _has(node, "freq"):
            val = _text(node)
            if val.startswith("S"):
                spoken = val
            elif val.startswith("W"):
                written = val
    if not any([stars, spoken, written]):
        return None
    return {"stars": stars, "spoken": spoken, "written": written}


def _inflections(head_nodes: list[HtmlElement]) -> list[dict]:
    mapping = {
        "pluralform": "plural",
        "pasttense": "past",
        "pastpart": "past_participle",
        "prespart": "present_participle",
        "t3perssing": "third_person",
        "superl": "superlative",
        "ptandpp": "past_and_past_participle",
    }
    out = []
    for node in head_nodes:
        for cls, kind in mapping.items():
            if _has(node, cls):
                form = _text(node)
                if form:
                    out.append({"type": kind, "form": form})
    return out


def _top_senses(container: HtmlElement) -> list[HtmlElement]:
    out = []
    for sense in container.xpath(_xpath_class("sense")):
        if _ancestor_has(sense, SENSE_SKIP_ANCESTORS, stop=container):
            continue
        if any(_has(a, "sense") for a in _ancestors(sense, stop=container)):
            continue
        out.append(sense)
    return out


def _subsenses(sense: HtmlElement) -> list[HtmlElement]:
    out = []
    for sub in sense.xpath(_xpath_class("subsense")):
        if _ancestor_has(sub, SENSE_SKIP_ANCESTORS, stop=sense):
            continue
        if any(_has(a, "subsense") for a in _ancestors(sub, stop=sense)):
            continue
        out.append(sub)
    return out


def _sense_def(sense: HtmlElement) -> dict | None:
    for node in sense.xpath(_xpath_class("def")):
        if _ancestor_has(node, DEF_SKIP_CLASSES | {"collobox", "thesbox", "exponent"}, stop=sense):
            continue
        if any(_has(a, "subsense") for a in _ancestors(node, stop=sense)):
            continue
        pair = extract_definition(node)
        if pair["en"] or pair["zh"]:
            return pair
    return None


def _fullforms_in_sense(sense: HtmlElement) -> list[str]:
    """Sense-level fullforms sitting beside .def, not those already inside <en>."""
    out = []
    for node in sense.xpath(_xpath_class("fullform")):
        if any(_has(a, "def") for a in _ancestors(node, stop=sense)):
            continue
        if any(_has(a, "subsense") for a in _ancestors(node, stop=sense)):
            continue
        text = _lexical(_text(node))
        if text and text not in out:
            out.append(text)
    return out


def _with_fullforms(en: str | None, forms: list[str]) -> str | None:
    if not forms:
        return en
    remaining = [f for f in forms if f.casefold() not in (en or "").casefold()]
    if not remaining:
        return en
    joined = " / ".join(remaining)
    if not en:
        return joined
    stripped = en.strip()
    if _ABBR_OF_RE.search(stripped):
        return stripped.rstrip(".") + " " + joined
    return stripped + " (" + joined + ")"


def _sense_number(sense: HtmlElement) -> str | None:
    for node in sense.xpath(_xpath_class("sensenum")):
        if any(_has(a, "subsense") for a in _ancestors(node, stop=sense)):
            continue
        return empty_to_none(_text(node).strip("."))
    return None


def _lexunits(sense: HtmlElement) -> list[str]:
    out = []
    for node in sense.xpath(_xpath_class("lexunit")):
        if any(_has(a, "subsense") for a in _ancestors(node, stop=sense)):
            continue
        if _ancestor_has(node, {"menuitem"}, stop=sense):
            continue
        text = _text(node)
        if text and text not in out:
            out.append(text)
    return out


def _patterns(sense: HtmlElement) -> list[str]:
    out = []
    for cls in ("propform", "propformprep"):
        for node in sense.xpath(_xpath_class(cls)):
            if _ancestor_has(node, {"example", "exas", "exaen", "collobox", "thesbox"}, stop=sense):
                continue
            text = _text(node)
            if text and text not in out:
                out.append(text)
    return out


def _signpost(sense: HtmlElement) -> dict | None:
    node = None
    for cand in sense.xpath(_xpath_class("signpost")):
        if any(_has(a, "subsense") for a in _ancestors(cand, stop=sense)):
            continue
        node = cand
        break
    if node is None:
        return None
    pair = _bilingual_pair(node, ("en", "signen"), ("tran", "sign"))
    if pair["en"] is None and pair["zh"] is None:
        pair["en"] = empty_to_none(_text(node))
    if pair["en"] is None and pair["zh"] is None:
        return None
    return pair


def _parse_sense(sense: HtmlElement, sense_id: str) -> dict:
    subs = []
    for i, sub in enumerate(_subsenses(sense), start=1):
        sid = _anchor_before(sub) or f"{sense_id}.{i}"
        subs.append(_parse_sense(sub, sid))
    definition = _sense_def(sense) or {"en": None, "zh": None}
    definition["en"] = _with_fullforms(definition.get("en"), _fullforms_in_sense(sense))
    if definition["en"] is None and definition["zh"] is None and not subs:
        # crossref-only sense still valid
        pass
    lexunits = _lexunits(sense)
    phrases = []
    for j, lex in enumerate(lexunits, start=1):
        phrases.append(
            {
                "id": f"{sense_id}#lu{j}",
                "type": "lexical_unit",
                "text": lex,
                "definition": definition if not subs else {"en": None, "zh": None},
                "labels": [],
                "sense_id": sense_id,
                "patterns": [],
            }
        )
    grammar = []
    for node in sense.xpath(_xpath_class("gram")):
        if any(_has(a, "subsense") for a in _ancestors(node, stop=sense)):
            continue
        grammar.extend(_split_grammar(_text(node)))
    return {
        "id": sense_id,
        "number": _sense_number(sense),
        "signpost": _signpost(sense),
        "grammar": grammar,
        "labels": _labels_in(sense, "sense"),
        "patterns": _patterns(sense),
        "lexunits": lexunits,
        "definition": definition,
        "cross_refs": _cross_refs(sense),
        "phrases": phrases,
        "senses": subs,
    }


def _slug(text: str) -> str:
    text = normalize_lookup(text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:80] or "x"


def _collocations(entry: HtmlElement, entry_id: str) -> list[dict]:
    out = []
    for i, col in enumerate(entry.xpath(_xpath_class("collocate")), start=1):
        if not _ancestor_has(col, {"collobox"}, stop=entry):
            continue
        text_el = _first(col, "colloc")
        if text_el is None:
            text_el = _first(col, "collo")
        text = _text(text_el) if text_el is not None else _text(col)
        if not text:
            continue
        gloss_el = _first(col, "collgloss")
        definition = {"en": None, "zh": None}
        if gloss_el is not None:
            g = _text(gloss_el).strip("()= ")
            definition["en"] = empty_to_none(g)
        out.append(
            {
                "id": f"{entry_id}#col{i}",
                "type": "collocation",
                "text": text,
                "definition": definition,
                "labels": [],
                "sense_id": None,
                "patterns": [],
            }
        )
    return out


def _parse_phrasal(pv: HtmlElement, parent_id: str, parent_hwd: str, mdx_key: str) -> dict:
    hwd_el = _first(pv, "phrvbhwd")
    headword = _text(hwd_el) if hwd_el is not None else _text(_first(pv, "entryhead"))
    headword = collapse_ws(headword.replace("↔", " ↔ "))
    anchor = _anchor_before(pv) or f"{parent_id}#pv:{_slug(headword)}"
    head_nodes = _head_region_nodes(pv)
    labels = []
    for node in head_nodes:
        if _has(node, "registerlab") or _has(node, "geo") or _has(node, "ac"):
            value = _text(node)
            if value:
                cls = "registerlab" if _has(node, "registerlab") else ("geo" if _has(node, "geo") else "ac")
                labels.append({"type": _label_type(value, cls), "value": value, "scope": "phrase"})
    senses = []
    for i, sense in enumerate(_top_senses(pv), start=1):
        sid = _anchor_before(sense) or f"{anchor}#s{i}"
        senses.append(_parse_sense(sense, sid))
    grammar = _head_grammar(head_nodes)
    return {
        "id": anchor,
        "kind": "phrasal_verb",
        "headword": headword,
        "display": headword,
        "homograph": None,
        "source": {"mdx_keys": [mdx_key], "anchor": anchor},
        "pronunciations": [],
        "frequency": None,
        "inflections": [],
        "pos_groups": [
            {
                "pos": ["phrasal verb"],
                "grammar": grammar,
                "labels": labels,
                "senses": senses,
            }
        ],
        "phrases": [],
        "cross_refs": _cross_refs(pv),
        "parent": {"id": parent_id, "headword": parent_hwd, "relation": "phrasal_verb"},
        "notes": [],
    }


def _parse_runon(runon: HtmlElement, parent_id: str, parent_hwd: str, mdx_key: str) -> dict:
    deriv = _first(runon, "deriv")
    headword = strip_leading_dash(_text(deriv) if deriv is not None else _text(runon))
    headword = re.sub(r"^—\s*", "", headword)
    # deriv often includes trailing pos if malformed; take first token-ish
    if deriv is not None:
        headword = strip_leading_dash(_text(deriv))
    anchor = _anchor_before(runon) or f"{parent_id}#deriv:{_slug(headword)}"
    prons = []
    for codes in runon.xpath(_xpath_class("proncodes")):
        prons.extend(_pronunciations(codes.getparent() if codes.getparent() is not None else runon))
    if not prons:
        prons = _pronunciations(runon)
    pos = []
    for node in runon.xpath(_xpath_class("pos")):
        pos.extend(_split_pos(_text(node)))
    grammar = []
    for node in runon.xpath(_xpath_class("gram")):
        grammar.extend(_split_grammar(_text(node)))
    labels = _labels_in(runon, "entry")
    defn = _sense_def(runon)
    senses = []
    if defn and (defn.get("en") or defn.get("zh")):
        senses.append(
            {
                "id": f"{anchor}#s1",
                "number": None,
                "signpost": None,
                "grammar": [],
                "labels": [],
                "patterns": [],
                "lexunits": [],
                "definition": defn,
                "cross_refs": [],
                "phrases": [],
                "senses": [],
            }
        )
    note = "no independent definition; run-on of " + parent_hwd
    return {
        "id": anchor,
        "kind": "derived",
        "headword": headword,
        "display": headword,
        "homograph": None,
        "source": {"mdx_keys": [mdx_key], "anchor": anchor},
        "pronunciations": prons,
        "frequency": None,
        "inflections": [],
        "pos_groups": [{"pos": pos or ["unknown"], "grammar": grammar, "labels": labels, "senses": senses}],
        "phrases": [],
        "cross_refs": _cross_refs(runon),
        "parent": {"id": parent_id, "headword": parent_hwd, "relation": "runon"},
        "notes": [] if senses else [note],
    }


def _main_entries(root: HtmlElement) -> list[HtmlElement]:
    out = []
    for el in root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " entry ")]'):
        if any(_has(a, "entry") or _has(a, "phrvbentry") for a in _ancestors(el)):
            continue
        hwds = [n for n in el.xpath(_xpath_class("hwd")) if not _ancestor_has(n, {"phrvbentry", "runon"}, stop=el)]
        if hwds:
            out.append(el)
    return out


def _has_def(root: HtmlElement) -> bool:
    return bool(root.xpath(_xpath_class("def")))


@dataclass
class LookupHit:
    norm: str
    entry_id: str
    sense_id: str | None
    match: str
    headword: str
    key_raw: str


@dataclass
class ParseResult:
    entries: list[dict] = field(default_factory=list)
    lookups: list[LookupHit] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    record_kind: str = "converted"
    main_headwords: list[str] = field(default_factory=list)
    derived_headwords: list[str] = field(default_factory=list)


def _add_lookup(result: ParseResult, key_raw: str, entry: dict, match: str, sense_id: str | None = None) -> None:
    for norm in lookup_keys_for(key_raw):
        result.lookups.append(
            LookupHit(
                norm=norm,
                entry_id=entry["id"],
                sense_id=sense_id,
                match=match,
                headword=entry["headword"],
                key_raw=key_raw,
            )
        )


def _walk_senses(senses: list[dict]) -> Iterable[dict]:
    for sense in senses:
        yield sense
        yield from _walk_senses(sense.get("senses") or [])


def _lookups_for_entry(result: ParseResult, entry: dict, extra_keys: list[str] | None = None) -> None:
    _add_lookup(result, entry["headword"], entry, "headword")
    if entry.get("display") and entry["display"] != entry["headword"]:
        _add_lookup(result, entry["display"], entry, "display")
    for inf in entry.get("inflections") or []:
        _add_lookup(result, inf["form"], entry, "inflection")
    for key in extra_keys or []:
        _add_lookup(result, key, entry, "mdx_key")
    for group in entry.get("pos_groups") or []:
        for sense in _walk_senses(group.get("senses") or []):
            for lex in sense.get("lexunits") or []:
                for variant in phrase_lookup_keys(lex):
                    _add_lookup(result, variant, entry, "phrase", sense["id"])
                extras = []
                # lexvar handled as patterns already in sense.patterns
            for pat in sense.get("patterns") or []:
                for variant in phrase_lookup_keys(pat):
                    _add_lookup(result, variant, entry, "phrase_pattern", sense["id"])
            for phrase in sense.get("phrases") or []:
                extras = []
                for variant in phrase_lookup_keys(phrase["text"], extras):
                    _add_lookup(result, variant, entry, "phrase", sense["id"])
    for phrase in entry.get("phrases") or []:
        for variant in phrase_lookup_keys(phrase["text"]):
            _add_lookup(result, variant, entry, phrase["type"], None)
    if entry["kind"] == "phrasal_verb":
        for variant in phrase_lookup_keys(entry["headword"]):
            _add_lookup(result, variant, entry, "phrasal_verb")
        for group in entry.get("pos_groups") or []:
            for sense in _walk_senses(group.get("senses") or []):
                for pat in sense.get("patterns") or []:
                    for variant in phrase_lookup_keys(pat):
                        _add_lookup(result, variant, entry, "phrase_pattern", sense["id"])


def _collect_lexvar(sense_el: HtmlElement) -> list[str]:
    out = []
    for node in sense_el.xpath(_xpath_class("lexvar")):
        text = _text(node)
        if text:
            out.append(text)
    for node in sense_el.xpath(_xpath_class("variant")):
        # skip varitype labels like "also"
        text = _text(node)
        # prefer lexvar inside
        inner = _first(node, "lexvar")
        if inner is not None:
            continue
        if text and not text.casefold().startswith("also"):
            out.append(text)
    return out


def _attach_lexvar_patterns(entry_el: HtmlElement, entry: dict) -> None:
    """Add visible lexicographic variants (e.g. take something into account)."""
    id_to_sense = {}
    for group in entry["pos_groups"]:
        for sense in _walk_senses(group["senses"]):
            id_to_sense[sense["id"]] = sense
    for sense_el in _top_senses(entry_el) + [
        sub for s in _top_senses(entry_el) for sub in _subsenses(s)
    ]:
        anchor = _anchor_before(sense_el)
        variants = _collect_lexvar(sense_el)
        if not variants:
            continue
        target = None
        if anchor and anchor in id_to_sense:
            target = id_to_sense[anchor]
        else:
            # match by number
            num = _sense_number(sense_el)
            for sense in id_to_sense.values():
                if num and sense.get("number") == num:
                    target = sense
                    break
        if target is None and id_to_sense:
            # first sense as last resort only if one sense
            if len(id_to_sense) == 1:
                target = next(iter(id_to_sense.values()))
        if target is None:
            continue
        for var in variants:
            if var not in target["patterns"]:
                target["patterns"].append(var)


def parse_html(mdx_key: str, raw_html: str) -> ParseResult:
    result = ParseResult()
    try:
        root = _clean_root(raw_html)
    except Exception as exc:  # noqa: BLE001
        result.record_kind = "error"
        result.issues.append({"key": mdx_key, "reason": f"html_parse:{type(exc).__name__}: {exc}", "status": "error"})
        return result

    entries_el = _main_entries(root)
    if not entries_el:
        faq = root.xpath('//*[contains(@class, "dict-faq")]')
        if faq:
            result.record_kind = "excluded_aux"
            result.issues.append(
                {
                    "key": mdx_key,
                    "reason": "front_matter_not_headword",
                    "status": "excluded_aux",
                    "locator": "class=dict-faq",
                }
            )
            return result
        result.record_kind = "error"
        result.issues.append({"key": mdx_key, "reason": "no_entry_node", "status": "error"})
        return result

    has_def = _has_def(root)
    has_cross = bool(root.xpath(_xpath_class("crossref")))

    for entry_el in entries_el:
        head_nodes = _head_region_nodes(entry_el)
        head_ids = {id(n) for n in head_nodes}
        headword = _headword(entry_el, head_ids)
        if not headword:
            result.issues.append({"key": mdx_key, "reason": "missing_headword", "status": "partial"})
            continue
        homograph = _homograph(head_nodes)
        anchor = _anchor_before(entry_el)
        if not anchor:
            slug = _slug(headword)
            hom = homograph or 1
            anchor = f"key:{slug}:{hom}"
        pos = _head_pos(head_nodes)
        grammar = _head_grammar(head_nodes)
        labels = []
        for node in head_nodes:
            if _has(node, "registerlab") or _has(node, "geo") or _has(node, "ac"):
                value = _text(node)
                if not value:
                    continue
                cls = "registerlab" if _has(node, "registerlab") else ("geo" if _has(node, "geo") else "ac")
                labels.append({"type": _label_type(value, cls), "value": value, "scope": "pos"})
        senses = []
        for i, sense_el in enumerate(_top_senses(entry_el), start=1):
            sid = _anchor_before(sense_el) or f"{anchor}#s{i}"
            senses.append(_parse_sense(sense_el, sid))
        kind = "word"
        if not has_def and has_cross:
            kind = "see_also"
        notes = []
        if kind == "see_also":
            notes.append("no_standard_def; cross-reference entry")
        entry = {
            "id": anchor,
            "kind": kind,
            "headword": headword,
            "display": headword,
            "homograph": homograph,
            "source": {"mdx_keys": [mdx_key], "anchor": anchor},
            "pronunciations": _head_prons(head_nodes),
            "frequency": _frequency(head_nodes),
            "inflections": _inflections(head_nodes),
            "pos_groups": [
                {
                    "pos": pos,
                    "grammar": grammar,
                    "labels": labels,
                    "senses": senses,
                }
            ],
            "phrases": _collocations(entry_el, anchor),
            "cross_refs": _cross_refs(entry_el) if kind == "see_also" else [x for x in _tail_cross_refs(entry_el)],
            "parent": None,
            "notes": notes,
        }
        _attach_lexvar_patterns(entry_el, entry)
        result.entries.append(entry)
        result.main_headwords.append(headword)

        for pv in entry_el.xpath(_xpath_class("phrvbentry")):
            if any(_has(a, "phrvbentry") for a in _ancestors(pv, stop=entry_el)):
                continue
            parsed_pv = _parse_phrasal(pv, entry["id"], headword, mdx_key)
            result.entries.append(parsed_pv)

        for runon in entry_el.xpath(_xpath_class("runon")):
            if any(_has(a, "runon") for a in _ancestors(runon, stop=entry_el)):
                continue
            derived = _parse_runon(runon, entry["id"], headword, mdx_key)
            result.entries.append(derived)
            result.derived_headwords.append(derived["headword"])

    key_n = normalize_lookup(mdx_key)
    main_n = {normalize_lookup(h) for h in result.main_headwords}
    deriv_n = {normalize_lookup(h) for h in result.derived_headwords}

    locator = key_n in deriv_n and key_n not in main_n
    if locator:
        result.record_kind = "converted_derived_locator"
    elif any(e["kind"] == "see_also" for e in result.entries) and not any(
        e["kind"] == "word" and any(s.get("definition", {}).get("en") or s.get("definition", {}).get("zh") for g in e["pos_groups"] for s in g["senses"])
        for e in result.entries
    ):
        result.record_kind = "converted_crossref"
    elif result.issues:
        result.record_kind = "converted_partial"
    else:
        result.record_kind = "converted"

    for entry in result.entries:
        extra = []
        derived_here = entry["kind"] == "derived" and normalize_lookup(entry["headword"]) == key_n
        if not locator or derived_here:
            extra.append(mdx_key)
        if locator and not derived_here:
            continue
        _lookups_for_entry(result, entry, extra_keys=extra)
        if derived_here:
            _add_lookup(result, mdx_key, entry, "derived_locator")

    if locator:
        # Keep only lookups that belong to the derived form (and its own phrases).
        keep_ids = {e["id"] for e in result.entries if e["kind"] == "derived" and normalize_lookup(e["headword"]) == key_n}
        result.lookups = [h for h in result.lookups if h.entry_id in keep_ids]

    if not result.entries:
        result.record_kind = "error"
        result.issues.append({"key": mdx_key, "reason": "no_entries_emitted", "status": "error"})
    return result


def _head_prons(head_nodes: list[HtmlElement]) -> list[dict]:
    out = []
    seen = set()
    for node in head_nodes:
        if _has(node, "proncodes"):
            for item in _pronunciations(node):
                key = (item["ipa"], item["accent"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
        elif _has(node, "pron") and not _has(node, "amevarpron"):
            ipa = empty_to_none(_ipa_text(node))
            if ipa and ("br", ipa) not in {(a, i) for i, a in seen}:
                key = (ipa, "br")
                if key not in seen:
                    seen.add(key)
                    out.append({"ipa": ipa, "accent": "br", "raw": ipa})
    return out


def _tail_cross_refs(entry: HtmlElement) -> list[dict]:
    out = []
    for tail in entry.xpath(_xpath_class("tail")):
        out.extend(_cross_refs(tail))
    return out
