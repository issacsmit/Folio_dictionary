"""Dump no-def shapes, run-out senses, take-account variants, and anchors."""
from __future__ import annotations

import importlib
import re
import sys
import types
from collections import Counter
from pathlib import Path

from lxml import html as lhtml

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "_inspect"
SOURCE = ROOT / "电子词典" / "电脑版~朗文当代第六版英汉"


def load_mdx():
    reader_path = next((ROOT / "tmp/mdx-audit-uv-cache/archive-v0").glob("*/readmdict/readmdict.py")).parent
    pkg = types.ModuleType("audit_readmdict")
    pkg.__path__ = [str(reader_path)]
    sys.modules[pkg.__name__] = pkg
    reader = importlib.import_module("audit_readmdict.readmdict")
    return reader.MDX(str(next(SOURCE.glob("*.mdx"))))


def main() -> None:
    mdx = load_mdx()
    want = {
        "aforethought", "Allies", "Ascot", "all fours", "threescore",
        "propagate", "propagation", "account", "run", "point", "cold", "light",
    }
    got = {}
    no_def_classes = Counter()
    no_def_tags = Counter()
    for rawkey, rawval in mdx.items():
        key = rawkey.decode("utf-8")
        val = rawval.decode("utf-8")
        if key in want:
            got[key] = val
        if not val.strip().startswith("@@@LINK=") and 'class="def' not in val and "class='def" not in val:
            root = lhtml.fromstring(val)
            no_def_classes.update(
                c for el in root.iter() if hasattr(el, "get") for c in (el.get("class") or "").split()
            )
            no_def_tags.update(el.tag for el in root.iter() if hasattr(el, "tag") and isinstance(el.tag, str))
    OUT.mkdir(exist_ok=True)
    (OUT / "no_def_classes.txt").write_text(
        "classes " + str(no_def_classes.most_common(40)) + "\n tags " + str(no_def_tags.most_common(20)),
        encoding="utf-8",
    )
    for k in ["aforethought", "Allies", "Ascot", "all fours", "threescore"]:
        raw = got[k]
        root = lhtml.fromstring(raw)
        for bad in root.xpath("//script|//link"):
            bad.getparent().remove(bad)
        (OUT / f"{k}.html").write_text(lhtml.tostring(root, encoding="unicode")[:30000], encoding="utf-8")

    # anchors
    for k in ["propagate", "propagation"]:
        raw = got[k]
        names = re.findall(r'name="([^"]+)"', raw)
        hwds = re.findall(r'class="hwd">([^<]+)', raw)
        (OUT / f"{k}_anchors.txt").write_text(
            f"len={len(raw)}\nhwds={hwds}\nfirst_names={names[:15]}\n",
            encoding="utf-8",
        )

    # run out / take account snippets
    run = got["run"]
    acc = got["account"]
    chunks = []
    for label, raw, pat in [
        ("run_out", run, r'phrvbhwd">run out.{0,2500}'),
        ("run_out_of", run, r'run out of.{0,400}'),
        ("take_account", acc, r'take account.{0,1500}'),
        ("into_account", acc, r'into account.{0,800}'),
        ("point_heads", got["point"], r'class="entryhead".{0,500}'),
        ("point_pos", got["point"], r'class="pos">.{0,40}'),
        ("threescore_def", got["threescore"], r'class="def".{0,400}'),
    ]:
        ms = re.findall(pat, raw, flags=re.I | re.S)
        chunks.append(f"## {label} n={len(ms)}")
        for m in ms[:6]:
            chunks.append(re.sub(r"\s+", " ", m)[:800])
            chunks.append("")
    (OUT / "phrase_snippets.txt").write_text("\n".join(chunks), encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
