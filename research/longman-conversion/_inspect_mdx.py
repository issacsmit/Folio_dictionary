"""Inspect live MDX keys for shared bodies, no-def records, phrases, runons."""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
import types
from collections import Counter
from pathlib import Path

from lxml import html as lhtml
from lxml.html import HtmlElement

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "_inspect"
SOURCE = ROOT / "电子词典" / "电脑版~朗文当代第六版英汉"


def load_mdx():
    reader_path = next((ROOT / "tmp/mdx-audit-uv-cache/archive-v0").glob("*/readmdict/readmdict.py")).parent
    pkg = types.ModuleType("audit_readmdict")
    pkg.__path__ = [str(reader_path)]
    sys.modules[pkg.__name__] = pkg
    reader = importlib.import_module("audit_readmdict.readmdict")
    mdx_path = next(SOURCE.glob("*.mdx"))
    return reader.MDX(str(mdx_path)), mdx_path


def classes(el: HtmlElement) -> list[str]:
    return (el.get("class") or "").split()


def has_class(el: HtmlElement, name: str) -> bool:
    return name in classes(el)


def snippet_runon(raw: str) -> str:
    m = re.search(r'<span class="runon".{0,800}', raw)
    return m.group(0) if m else "(no runon)"


def snippet_phrvbs(raw: str) -> str:
    m = re.search(r'<span class="phrvb[^"]*".{0,500}', raw)
    if not m:
        m = re.search(r'class="phrvbhwd".{0,400}', raw)
    return m.group(0) if m else "(no phrvb)"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    mdx, mdx_path = load_mdx()
    print("mdx", mdx_path, "len", len(mdx), flush=True)
    want = {
        "propagate", "propagation", "refract", "refraction", "study", "studies",
        "threescore", "go", "went", "index", "indices", "run", "account",
        "fish", "aforethought", "Allies", "Ascot",
        "run out", "run out of", "take into account", "take account of",
    }
    found = {}
    no_def = []
    body_hash_keys = {}
    link_targets = Counter()
    n = 0
    n_link = 0
    n_html = 0
    decode_errors = 0
    replacement = 0
    for rawkey, rawval in mdx.items():
        n += 1
        try:
            key = rawkey.decode("utf-8")
        except UnicodeDecodeError:
            decode_errors += 1
            key = rawkey.decode("utf-8", "replace")
        try:
            val = rawval.decode("utf-8")
        except UnicodeDecodeError:
            decode_errors += 1
            val = rawval.decode("utf-8", "replace")
        if "\ufffd" in val or "\ufffd" in key:
            replacement += 1
        if val.strip().startswith("@@@LINK="):
            n_link += 1
            tgt = val.strip()[8:]
            link_targets[tgt] += 1
            if key.casefold() in want or tgt.casefold() in want:
                found.setdefault(key, val[:200])
            continue
        n_html += 1
        h = hashlib.sha1(rawval).hexdigest()[:12]
        body_hash_keys.setdefault(h, []).append(key)
        if key.casefold() in {x.casefold() for x in want}:
            found[key] = val
        if "<span class=\"def\"" not in val and "class='def'" not in val and 'class="def ' not in val:
            no_def.append(key)
    print("iter", n, "link", n_link, "html", n_html, "decode_err", decode_errors, "replacement", replacement)
    print("no_def", len(no_def))
    shared = {h: ks for h, ks in body_hash_keys.items() if len(ks) > 1}
    print("shared_bodies", len(shared), "max_share", max((len(v) for v in shared.values()), default=0))
    share_sizes = Counter(len(v) for v in shared.values())
    print("share_size_hist", dict(sorted(share_sizes.items())[:20]))

    # report wanted keys
    report = []
    for k in sorted(want):
        hits = [x for x in found if x.casefold() == k.casefold()]
        report.append(f"## query {k} hits={hits}")
        for h in hits:
            v = found[h]
            if v.strip().startswith("@@@LINK="):
                report.append(f"{h} LINK {v.strip()}")
            else:
                root = lhtml.fromstring(v)
                hwds = [" ".join(x.text_content().split()) for x in root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " hwd ")]')]
                runons = [" ".join(x.text_content().split())[:120] for x in root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " runon ")]')]
                phr = [" ".join(x.text_content().split())[:80] for x in root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " phrvbhwd ")]')[:30]]
                lex = [" ".join(x.text_content().split())[:80] for x in root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " lexunit ")]')[:20]]
                phrases = [" ".join(x.text_content().split())[:80] for x in root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " phrasetext ")]')[:20]]
                report.append(f"{h} html={len(v)} hwds={hwds[:8]} n_runon={len(runons)} n_phrvb={len(phr)} n_lex={len(lex)}")
                report.append("runons=" + str(runons[:8]))
                report.append("phrvb=" + str(phr[:25]))
                report.append("lex=" + str(lex[:20]))
                report.append("phrasetext=" + str(phrases[:20]))
                report.append("RUNON_HTML " + snippet_runon(v))
                report.append("PHRVB_HTML " + snippet_phrvbs(v))
    (OUT / "wanted.txt").write_text("\n".join(report), encoding="utf-8")

    # shared bodies involving wanted
    interesting_shared = []
    for h, ks in shared.items():
        if any(k.casefold() in {x.casefold() for x in want} for k in ks):
            interesting_shared.append(ks)
    (OUT / "shared_wanted.json").write_text(json.dumps(interesting_shared, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "no_def.json").write_text(json.dumps(no_def, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "share_stats.json").write_text(
        json.dumps(
            {
                "records": n,
                "links": n_link,
                "html": n_html,
                "decode_errors": decode_errors,
                "replacement_char": replacement,
                "no_def": len(no_def),
                "shared_body_groups": len(shared),
                "share_size_hist": dict(share_sizes),
                "largest_shares": sorted((ks for ks in shared.values()), key=len, reverse=True)[:15],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("no_def_sample", no_def[:30])
    print("largest_shares", sorted(shared.values(), key=len, reverse=True)[:8])
    print("wrote inspect files")


if __name__ == "__main__":
    main()
