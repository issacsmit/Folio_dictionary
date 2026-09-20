"""Query a Folio dictionary pack or its unpacked JSONL."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .normalize import fold_lookup, lookup_keys_for, normalize_lookup
from .paths import PACK_ZIP, UNPACKED_DIR


def _load_jsonl_text(text: str):
    for line in text.splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


def _load_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


_PACK_CACHE: tuple | None = None


def load_pack(pack: Path | None = None) -> tuple[dict, dict[str, dict], dict[str, list]]:
    global _PACK_CACHE
    pack = pack or PACK_ZIP
    stamp = (str(pack), pack.stat().st_mtime if pack.exists() else 0)
    if _PACK_CACHE and _PACK_CACHE[0] == stamp:
        return _PACK_CACHE[1]
    result = _load_pack(pack)
    _PACK_CACHE = (stamp, result)
    return result


def _load_pack(pack: Path) -> tuple[dict, dict[str, dict], dict[str, list]]:
    if pack.suffix.lower() == ".zip" and pack.is_file():
        with zipfile.ZipFile(pack) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            entries = {row["id"]: row for row in _load_jsonl_text(zf.read("entries.jsonl").decode("utf-8"))}
            lookup = {row["norm"]: row["matches"] for row in _load_jsonl_text(zf.read("lookup.jsonl").decode("utf-8"))}
        return manifest, entries, lookup
    if pack.is_dir():
        root = pack
    elif UNPACKED_DIR.is_dir() and (UNPACKED_DIR / "entries.jsonl").exists():
        root = UNPACKED_DIR
    else:
        raise FileNotFoundError(f"No pack at {pack}")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    entries = {row["id"]: row for row in _load_jsonl(root / "entries.jsonl")}
    lookup = {row["norm"]: row["matches"] for row in _load_jsonl(root / "lookup.jsonl")}
    return manifest, entries, lookup


def format_definition(defn: dict | None) -> str:
    defn = defn or {}
    en = defn.get("en")
    zh = defn.get("zh")
    if zh and en:
        return f"中文: {zh}\n    英文: {en}"
    if zh:
        return f"中文: {zh}"
    if en:
        return f"英文: {en}"
    return "（无独立释义）"


def format_entry(entry: dict, sense_id: str | None = None, match: str | None = None) -> str:
    lines = []
    hom = f"  {entry['homograph']}" if entry.get("homograph") else ""
    lines.append(f"词头: {entry.get('display') or entry['headword']}{hom}  [{entry.get('kind')}]")
    if match:
        lines.append(f"匹配: {match}")
    prons = []
    for p in entry.get("pronunciations") or []:
        label = {"br": "英", "us": "美", "unspecified": ""}.get(p.get("accent"), p.get("accent"))
        prons.append(f"{label} {p['ipa']}".strip())
    if prons:
        lines.append("音标: " + "  ".join(prons))
    if entry.get("parent"):
        par = entry["parent"]
        lines.append(f"关联: {par.get('relation')} → {par.get('headword')}")
    for group in entry.get("pos_groups") or []:
        pos = ", ".join(group.get("pos") or []) or "(no pos)"
        gram = ("  " + ", ".join(group.get("grammar") or [])) if group.get("grammar") else ""
        labs = "  " + ", ".join(l["value"] for l in group.get("labels") or []) if group.get("labels") else ""
        lines.append(f"词性: {pos}{gram}{labs}")

        def emit_sense(sense, indent="  ", force: bool = False):
            matched = force or sense_id is None or sense.get("id") == sense_id
            if not matched and not _sense_contains(sense, sense_id):
                return
            show = matched or sense.get("id") == sense_id
            num = sense.get("number") or ""
            sign = sense.get("signpost") or {}
            sign_t = sign.get("zh") or sign.get("en") or ""
            defn = sense.get("definition") or {}
            has_def = bool(defn.get("en") or defn.get("zh"))
            force_children = show or force
            if show and (has_def or not sense.get("senses")):
                head = indent + (f"{num}. " if num else "- ")
                if sign_t:
                    head += f"[{sign_t}] "
                lines.append(head + format_definition(defn).replace("\n", "\n" + indent + "  "))
                if sense.get("lexunits"):
                    lines.append(indent + "  词组: " + " | ".join(sense["lexunits"]))
                if sense.get("patterns"):
                    lines.append(indent + "  句型: " + " | ".join(sense["patterns"]))
            elif show and (num or sign_t):
                extra = f"[{sign_t}] " if sign_t else ""
                lines.append(indent + (f"{num}. " if num else "- ") + extra)
            for sub in sense.get("senses") or []:
                emit_sense(sub, indent + "  ", force=force_children)

        for sense in group.get("senses") or []:
            emit_sense(sense)
    phrases = entry.get("phrases") or []
    if phrases:
        lines.append("搭配:")
        for ph in phrases[:12]:
            bit = ph["text"]
            if ph.get("definition", {}).get("en") or ph.get("definition", {}).get("zh"):
                bit += " — " + (ph["definition"].get("zh") or ph["definition"].get("en") or "")
            lines.append("  · " + bit)
    if entry.get("cross_refs"):
        refs = "; ".join(x["text"] for x in entry["cross_refs"][:8])
        lines.append("参见: " + refs)
    if entry.get("notes"):
        lines.append("注: " + "; ".join(entry["notes"]))
    return "\n".join(lines)


def _sense_contains(sense: dict, sense_id: str) -> bool:
    if sense.get("id") == sense_id:
        return True
    return any(_sense_contains(s, sense_id) for s in sense.get("senses") or [])


MATCH_RANK = {
    "headword": 0,
    "display": 1,
    "mdx_key": 1,
    "derived_locator": 2,
    "alias": 3,
    "phrasal_verb": 4,
    "inflection": 5,
    "phrase": 6,
    "phrase_pattern": 6,
    "lexical_unit": 6,
    "collocation": 9,
}


def rank_matches(query_norm: str, matches: list[dict], query_exact: str | None = None) -> list[dict]:
    query_exact = query_exact if query_exact is not None else query_norm

    def score(m: dict) -> tuple:
        head_raw = m.get("headword") or ""
        head_exact = fold_lookup(head_raw)
        head_loose = normalize_lookup(head_raw)
        if head_exact == query_exact:
            exact = 0
        elif head_loose == query_norm:
            exact = 1
        else:
            exact = 2
        return (exact, MATCH_RANK.get(m.get("match") or "", 8), head_raw)

    return sorted(matches, key=score)


def collect_matches(text: str, lookup: dict[str, list]) -> list[dict]:
    exact = fold_lookup(text)
    loose = normalize_lookup(text)
    ordered: list[dict] = []
    seen: set[tuple] = set()
    for key in lookup_keys_for(text):
        for match in lookup.get(key) or []:
            ident = (match.get("entry_id"), match.get("sense_id"), match.get("match"), match.get("key_raw"))
            if ident in seen:
                continue
            seen.add(ident)
            ordered.append(match)
    return rank_matches(loose, ordered, query_exact=exact)


def query(text: str, pack: Path | None = None, limit: int = 8) -> str:
    _manifest, entries, lookup = load_pack(pack)
    matches = collect_matches(text, lookup)
    if not matches:
        return f"未命中: {text}  (norm={normalize_lookup(text)})"
    blocks = [f"查询: {text}  命中 {len(matches)} 条"]
    seen_entries = set()
    shown = 0
    for m in matches:
        eid = m["entry_id"]
        if eid in seen_entries:
            continue
        seen_entries.add(eid)
        entry = entries.get(eid)
        if not entry:
            blocks.append(f"失效引用: {m}")
            continue
        sense_id = m.get("sense_id") if MATCH_RANK.get(m.get("match") or "", 8) >= 6 else None
        blocks.append(format_entry(entry, sense_id=sense_id, match=m.get("match")))
        shown += 1
        if shown >= limit:
            break
    leftover = len({m["entry_id"] for m in matches}) - shown
    if leftover > 0:
        blocks.append(f"… 另有 {leftover} 条未展开")
    return "\n\n".join(blocks)
