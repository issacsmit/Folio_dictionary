"""Temporary inspector for Longman HTML structure. Not part of the product."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from lxml import html as lhtml
from lxml.html import HtmlElement

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "research" / "mdx-pilot" / "samples.raw.json"
OUT = Path(__file__).resolve().parent / "_inspect"


def classes(el: HtmlElement) -> list[str]:
    return (el.get("class") or "").split()


def has_class(el: HtmlElement, name: str) -> bool:
    return name in classes(el)


def xpath_class(name: str) -> str:
    return f'//*[contains(concat(" ", normalize-space(@class), " "), " {name} ")]'


def dump_tree(el: HtmlElement, depth: int = 0, max_depth: int = 7, lines: list[str] | None = None) -> list[str]:
    lines = lines if lines is not None else []
    if depth > max_depth:
        return lines
    cls = " ".join(classes(el))
    extra = ""
    interesting = {
        "hwd", "hyphenation", "pos", "pron", "amevarpron", "homnum", "sensenum",
        "signpost", "phrvbhwd", "lexunit", "runon", "def", "gram", "registerlab",
        "geo", "infllab", "crossref", "refhwd", "deriv", "relatedwd",
    }
    if interesting.intersection(classes(el)) or el.tag in ("en", "tran", "a"):
        extra = " TEXT=" + " ".join(el.text_content().split())[:140]
    lines.append("  " * depth + f"<{el.tag} class=\"{cls}\"{extra}>")
    skip_deep = {
        "collobox", "thesbox", "usagebox", "grambox", "f2nbox", "etymbox",
        "popexa", "popthes", "popcollo", "popphrase", "popwf", "pope_menu",
        "entrymenu", "exas", "example", "verbtable", "buttons", "expandable",
    }
    if skip_deep.intersection(classes(el)) and depth > 0:
        lines[-1] += " ..."
        return lines
    for child in el:
        if isinstance(child, HtmlElement):
            dump_tree(child, depth + 1, max_depth, lines)
    return lines


def summarize(name: str, raw: str) -> str:
    out = [f"# {name}", f"len={len(raw)}"]
    if raw.strip().startswith("@@@LINK="):
        out.append(raw.strip())
        return "\n".join(out)
    root = lhtml.fromstring(raw)
    out.append("top_classes=" + str(Counter(c for el in root.iter() if isinstance(el, HtmlElement) for c in classes(el)).most_common(40)))
    entries = [e for e in root.xpath(xpath_class("entry")) if not e.xpath('ancestor::*[contains(concat(" ", normalize-space(@class), " "), " entry ")]')]
    out.append(f"n_top_entry={len(entries)}")
    for i, e in enumerate(entries):
        hwd = [" ".join(x.text_content().split()) for x in e.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " hwd ")]')[:3]]
        head_pos = []
        for child in e:
            if not isinstance(child, HtmlElement):
                continue
            if has_class(child, "entryhead"):
                head_pos = [" ".join(x.text_content().split()) for x in child.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " pos ")]')]
        child_cls = [" ".join(classes(c)) or c.tag for c in e if isinstance(c, HtmlElement)]
        out.append(f"## entry {i} hwd={hwd} head_pos={head_pos} n_direct={len(child_cls)}")
        out.append("direct=" + str(child_cls))
        # senses that are not inside auxiliary boxes
        senses = e.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " sense ")]')
        main_senses = []
        for s in senses:
            anc = " ".join(" ".join(classes(a)) for a in s.xpath("ancestor::*"))
            if any(box in anc for box in ("collobox", "thesbox", "usagebox", "grambox", "f2nbox", "etymbox", "popexa", "popthes", "popcollo", "popphrase", "popwf", "phrvbs", "phrvbentry")):
                continue
            main_senses.append(s)
        out.append(f"n_sense_all={len(senses)} n_sense_mainish={len(main_senses)}")
        for j, s in enumerate(main_senses[:12]):
            defs = s.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " def ")]')
            def_txt = [" ".join(d.text_content().split())[:160] for d in defs[:3]]
            lex = [" ".join(x.text_content().split())[:80] for x in s.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " lexunit ")]')[:4]]
            out.append(f"  sense{j} defs={def_txt} lex={lex}")
        phrvbs = e.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " phrvbentry ")]')
        out.append(f"n_phrvbentry={len(phrvbs)}")
        for j, p in enumerate(phrvbs[:8]):
            h = [" ".join(x.text_content().split()) for x in p.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " phrvbhwd ")]')[:2]]
            defs = [" ".join(d.text_content().split())[:120] for d in p.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " def ")]')[:2]]
            out.append(f"  phr{j} {h} defs={defs}")
        runons = e.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " runon ")]')
        out.append(f"n_runon={len(runons)}")
        for j, r in enumerate(runons[:8]):
            out.append("  runon" + str(j) + " " + " ".join(r.text_content().split())[:160])
        out.append("TREE:")
        out.extend(dump_tree(e, max_depth=5)[:220])
    return "\n".join(out)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    data = json.loads(SAMPLES.read_text(encoding="utf-8"))
    for name in [
        "throughout", "fish", "chatbot", "indices", "studies", "went",
        "propagation", "refraction", "almighty", "children", "evanescent",
        "discontinuity",
    ]:
        text = summarize(name, data[name][0])
        (OUT / f"{name}.txt").write_text(text, encoding="utf-8")
        print("wrote", name, "chars", len(text))
    # also dump first 4000 chars of simplified HTML for throughout/fish/propagation
    for name in ["throughout", "fish", "propagation", "indices", "went", "chatbot"]:
        raw = data[name][0]
        root = lhtml.fromstring(raw)
        for bad in root.xpath("//script|//link|//style"):
            bad.getparent().remove(bad)
        pretty = lhtml.tostring(root, encoding="unicode")
        (OUT / f"{name}.html").write_text(pretty[:80000], encoding="utf-8")


if __name__ == "__main__":
    main()
