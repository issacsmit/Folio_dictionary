"""Dump study / v. / U. sense HTML for the four review bugs."""
from __future__ import annotations

import re
from pathlib import Path

from lxml import html as lhtml

from folio_ldoce.mdx_reader import iter_records, open_mdx

OUT = Path(__file__).resolve().parent / "_inspect"
WANT = {"study", "v.", "U.", "u.", "V.", "v", "U"}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    mdx, _ = open_mdx()
    found = {}
    for key, value, is_link, _t in iter_records(mdx):
        if key in WANT:
            found[key] = (is_link, value)
        if len(found) >= 4 and "study" in found and "v." in found and "U." in found:
            # keep scanning a bit for U/u.
            if len(found) >= 6:
                break
    for key, (is_link, value) in found.items():
        print(key, "link" if is_link else "html", len(value))
        (OUT / f"fix_{key.replace('.', '_')}.html").write_text(value, encoding="utf-8")
        if is_link:
            continue
        root = lhtml.fromstring(value)
        defs = root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " def ")]')
        print("  n_def", len(defs))
        for i, d in enumerate(defs[:8]):
            html = lhtml.tostring(d, encoding="unicode")[:400]
            print(f"  def{i}", re.sub(r"\s+", " ", html)[:300])
        ffs = root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " fullform ")]')
        print("  n_fullform", len(ffs))
        for i, f in enumerate(ffs[:8]):
            parent = f.getparent()
            pcls = parent.get("class") if parent is not None else None
            print("  fullform", i, repr(" ".join(f.itertext())[:80]), "parent", pcls)
            # previous sibling / following
            prev = f.getprevious()
            print("    prev", prev.tag if prev is not None else None, (prev.get("class") if prev is not None else None), repr(" ".join(prev.itertext())[:60] if prev is not None else ""))
            nxt = f.getnext()
            print("    next", nxt.tag if nxt is not None else None, (nxt.get("class") if nxt is not None else None))
            # parent html snippet
            if parent is not None:
                print("    parent_html", re.sub(r"\s+", " ", lhtml.tostring(parent, encoding="unicode"))[:400])

    # specifically study sense 3
    if "study" in found:
        raw = found["study"][1]
        # find literary/historical
        m = re.search(r".{200}literary/historical.{400}", raw)
        print("\nSTUDY SNIPPET")
        print(re.sub(r"\s+", " ", m.group(0)) if m else "not found")


if __name__ == "__main__":
    main()
