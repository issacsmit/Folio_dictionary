"""Stream the Longman MDX into a Folio dictionary pack."""
from __future__ import annotations

import hashlib
import json
import random
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import PACK_FORMAT, PACK_FORMAT_VERSION, PACK_ID, PARSER_VERSION
from .mdx_reader import inspect_reader, iter_records, open_mdx
from .normalize import lookup_keys_for, normalize_lookup
from .parse import ParseResult, parse_html
from .paths import OUTPUT_DIR, PACK_ZIP


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _merge_entry(existing: dict, incoming: dict, locator: bool) -> None:
    incoming_keys = incoming.get("source", {}).get("mdx_keys") or []
    bucket = existing.setdefault("source", {}).setdefault("mdx_keys", [])
    if locator and incoming.get("kind") != "derived":
        return
    for key in incoming_keys:
        if key not in bucket:
            bucket.append(key)


def _as_html(name: str, html_keys: set[str], html_fold: dict[str, str]) -> str | None:
    if name in html_keys:
        return name
    return html_fold.get(normalize_lookup(name))


def _resolve_link(
    start: str,
    alias_map: dict[str, str],
    fold_map: dict[str, str],
    html_keys: set[str],
    html_fold: dict[str, str],
) -> tuple[str | None, str | None]:
    hit = _as_html(start, html_keys, html_fold)
    if hit:
        return hit, None
    seen: list[str] = []
    cur = start
    for _ in range(20):
        if cur in seen:
            return None, "cycle:" + "->".join(seen + [cur])
        seen.append(cur)
        nxt = alias_map.get(cur)
        if nxt is None:
            folded = fold_map.get(normalize_lookup(cur))
            if folded and folded != cur:
                cur = folded
                hit = _as_html(cur, html_keys, html_fold)
                if hit:
                    return hit, None
                nxt = alias_map.get(folded)
                if nxt is None:
                    return cur, None
            else:
                return cur, None
        nxt = nxt.split("#", 1)[0].strip()
        hit = _as_html(nxt, html_keys, html_fold)
        if hit:
            return hit, None
        cur = nxt
    return None, "too_long:" + "->".join(seen)


def convert(
    mdx_path: Path | None = None,
    out_dir: Path | None = None,
    zip_path: Path | None = None,
    limit: int | None = None,
) -> dict:
    out_dir = out_dir or OUTPUT_DIR
    unpacked = out_dir / "unpacked"
    zip_path = zip_path or (out_dir / PACK_ZIP.name)
    unpacked.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    rss_peak = None
    try:
        import psutil

        proc = psutil.Process()
        rss_peak = proc.memory_info().rss
    except Exception:  # noqa: BLE001
        proc = None

    mdx, path = open_mdx(mdx_path)
    reader_report = inspect_reader(mdx, path)

    entries: dict[str, dict] = {}
    lookups: dict[str, list[dict]] = defaultdict(list)
    ledger_rows: list[dict] = []
    issues: list[dict] = []
    alias_map: dict[str, str] = {}
    alias_records: list[tuple[str, str]] = []
    fold_map: dict[str, str] = {}
    html_keys: set[str] = set()
    key_entry_ids: dict[str, list[str]] = defaultdict(list)
    stats = Counter()
    bilingual_senses = 0
    english_only_senses = 0
    zh_only_senses = 0
    empty_senses = 0

    def bump_rss() -> None:
        nonlocal rss_peak
        if proc is None:
            return
        rss = proc.memory_info().rss
        if rss_peak is None or rss > rss_peak:
            rss_peak = rss

    def consider_senses(entry: dict) -> None:
        nonlocal bilingual_senses, english_only_senses, zh_only_senses, empty_senses

        def walk(senses):
            nonlocal bilingual_senses, english_only_senses, zh_only_senses, empty_senses
            for sense in senses:
                en = (sense.get("definition") or {}).get("en")
                zh = (sense.get("definition") or {}).get("zh")
                if en and zh:
                    bilingual_senses += 1
                elif en:
                    english_only_senses += 1
                elif zh:
                    zh_only_senses += 1
                else:
                    empty_senses += 1
                walk(sense.get("senses") or [])

        for group in entry.get("pos_groups") or []:
            walk(group.get("senses") or [])

    rng = random.Random(20260920)
    letter_buckets: dict[str, list[dict]] = defaultdict(list)

    def compact_sample(key: str, parsed: ParseResult) -> dict:
        senses = []
        for entry in parsed.entries:
            for group in entry.get("pos_groups") or []:
                for sense in group.get("senses") or []:
                    senses.append(
                        {
                            "entry": entry["headword"],
                            "kind": entry["kind"],
                            "pos": group.get("pos"),
                            "en": (sense.get("definition") or {}).get("en"),
                            "zh": (sense.get("definition") or {}).get("zh"),
                            "lexunits": sense.get("lexunits") or [],
                        }
                    )
        return {
            "key": key,
            "status": parsed.record_kind,
            "headwords": [e["headword"] for e in parsed.entries],
            "kinds": [e["kind"] for e in parsed.entries],
            "senses": senses[:12],
            "issue_count": len(parsed.issues),
        }

    n = 0
    for key, value, is_link, target in iter_records(mdx):
        n += 1
        stats["records"] += 1
        fold_map.setdefault(normalize_lookup(key), key)
        if is_link:
            stats["redirects"] += 1
            alias_map[key] = target or ""
            alias_records.append((key, target or ""))
            continue
        stats["non_redirects"] += 1
        html_keys.add(key)
        parsed: ParseResult = parse_html(key, value)
        stats[parsed.record_kind] += 1
        locator = parsed.record_kind == "converted_derived_locator"
        entry_ids = []
        for entry in parsed.entries:
            eid = entry["id"]
            if eid in entries:
                _merge_entry(entries[eid], entry, locator=locator)
            else:
                entries[eid] = entry
                consider_senses(entry)
                stats["entries_" + entry["kind"]] += 1
            entry_ids.append(eid)
            if not locator or entry["kind"] == "derived":
                key_entry_ids[key].append(eid)
        for hit in parsed.lookups:
            rec = {
                "entry_id": hit.entry_id,
                "sense_id": hit.sense_id,
                "match": hit.match,
                "headword": hit.headword,
                "key_raw": hit.key_raw,
            }
            existing = lookups[hit.norm]
            if rec not in existing:
                existing.append(rec)
        for issue in parsed.issues:
            issues.append(issue)
        ledger_rows.append(
            {
                "key": key,
                "status": parsed.record_kind,
                "entry_ids": entry_ids,
                "link_target": None,
                "reason": None,
                "issues": len(parsed.issues),
            }
        )
        letter = (key[:1] if key else "?").upper()
        if letter not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            letter = "#"
        if len(letter_buckets[letter]) < 3:
            letter_buckets[letter].append(compact_sample(key, parsed))
        if n % 2000 == 0:
            bump_rss()
            print(f"progress records={n} entries={len(entries)} lookups={len(lookups)}", flush=True)
        if limit is not None and n >= limit:
            break

    html_fold = {normalize_lookup(k): k for k in html_keys}
    # Resolve aliases (one ledger row per MDX record, including duplicate keys)
    for key, target in alias_records:
        resolved, err = _resolve_link(target, alias_map, fold_map, html_keys, html_fold)
        if err:
            status = "alias_cycle" if err.startswith("cycle") else "alias_unresolved"
            stats[status] += 1
            ledger_rows.append(
                {
                    "key": key,
                    "status": status,
                    "entry_ids": [],
                    "link_target": target,
                    "reason": err,
                    "issues": 1,
                }
            )
            issues.append({"key": key, "reason": err, "status": status, "target": target})
            continue
        target_key = resolved or ""
        ids = list(key_entry_ids.get(target_key) or [])
        if not ids:
            folded = fold_map.get(normalize_lookup(target_key))
            if folded:
                ids = list(key_entry_ids.get(folded) or [])
                target_key = folded
        if not ids:
            stats["alias_unresolved"] += 1
            ledger_rows.append(
                {
                    "key": key,
                    "status": "alias_unresolved",
                    "entry_ids": [],
                    "link_target": target,
                    "reason": f"missing:{target_key}",
                    "issues": 1,
                }
            )
            issues.append({"key": key, "reason": f"missing:{target_key}", "status": "alias_unresolved", "target": target})
            continue
        stats["alias_mapped"] += 1
        ledger_rows.append(
            {
                "key": key,
                "status": "alias_mapped",
                "entry_ids": ids,
                "link_target": target,
                "reason": None,
                "issues": 0,
            }
        )
        for eid in ids:
            entry = entries.get(eid)
            if not entry:
                continue
            rec = {
                "entry_id": eid,
                "sense_id": None,
                "match": "alias",
                "headword": entry["headword"],
                "key_raw": key,
            }
            for norm in lookup_keys_for(key):
                bucket = lookups[norm]
                if rec not in bucket:
                    bucket.append(rec)

    bump_rss()
    elapsed = time.perf_counter() - t0

    entries_path = unpacked / "entries.jsonl"
    lookup_path = unpacked / "lookup.jsonl"
    with entries_path.open("w", encoding="utf-8", newline="\n") as fh:
        for eid in sorted(entries):
            fh.write(json.dumps(entries[eid], ensure_ascii=False, separators=(",", ":")) + "\n")
    with lookup_path.open("w", encoding="utf-8", newline="\n") as fh:
        for norm in sorted(lookups):
            row = {"norm": norm, "matches": lookups[norm]}
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    ledger_path = out_dir / "ledger.jsonl"
    issues_path = out_dir / "issues.jsonl"
    with ledger_path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in ledger_rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with issues_path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in issues:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    counts = {
        "input_records": stats["records"],
        "input_redirects": stats["redirects"],
        "input_non_redirects": stats["non_redirects"],
        "entries": len(entries),
        "entries_word": stats["entries_word"],
        "entries_derived": stats["entries_derived"],
        "entries_phrasal_verb": stats["entries_phrasal_verb"],
        "entries_see_also": stats["entries_see_also"],
        "lookup_keys": len(lookups),
        "senses_bilingual": bilingual_senses,
        "senses_english_only": english_only_senses,
        "senses_zh_only": zh_only_senses,
        "senses_empty": empty_senses,
        "converted": stats["converted"],
        "converted_derived_locator": stats["converted_derived_locator"],
        "converted_crossref": stats["converted_crossref"],
        "converted_partial": stats["converted_partial"],
        "excluded_aux": stats["excluded_aux"],
        "alias_mapped": stats["alias_mapped"],
        "alias_unresolved": stats["alias_unresolved"],
        "alias_cycle": stats["alias_cycle"],
        "error": stats["error"],
        "issues": len(issues),
        "ledger_rows": len(ledger_rows),
    }
    files = ["manifest.json", "entries.jsonl", "lookup.jsonl"]
    manifest = {
        "format": PACK_FORMAT,
        "format_version": PACK_FORMAT_VERSION,
        "pack_id": PACK_ID,
        "parser_version": PARSER_VERSION,
        "generated_at": _now(),
        "source": {
            "name": "朗文当代第六版（英汉） MDX",
            "mdx_path": reader_report.path,
            "mdx_sha256": reader_report.sha256,
            "mdx_bytes": reader_report.file_bytes,
            "header": reader_report.header,
            "rights_note": "Source file identity only. This pack does not assert publisher authorization.",
        },
        "languages": {"headword": "en", "definition": ["en", "zh"]},
        "files": files,
        "counts": counts,
        "checksums": {
            "entries.jsonl": _sha256_file(entries_path),
            "lookup.jsonl": _sha256_file(lookup_path),
        },
        "content_policy": {
            "ai_backfill": False,
            "missing_zh": "null; keep English",
            "examples": False,
            "audio": False,
            "images": False,
        },
        "limitations": reader_report.notes
        + [
            "v1 keeps IPA, bilingual/English definitions, labels, phrases, derived run-ons and cross-references.",
            "Thesaurus, extra example banks, etymology, verb tables and word-family lists are excluded from main senses.",
        ],
    }
    manifest_path = unpacked / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["checksums"]["manifest.json"] = _sha256_file(manifest_path)

    pool = [row for rows in letter_buckets.values() for row in rows]
    typed = {
        "derived": [r for r in pool if "derived" in r["kinds"] or r["status"] == "converted_derived_locator"],
        "see_also": [r for r in pool if r["status"] == "converted_crossref"],
        "english_only": [r for r in pool if r["senses"] and all(not s.get("zh") and s.get("en") for s in r["senses"])],
        "bilingual": [r for r in pool if any(s.get("zh") and s.get("en") for s in r["senses"])],
        "poly": [r for r in pool if sum(1 for k in r["kinds"] if k == "word") > 1 or len(r["senses"]) >= 4],
    }
    picked = []
    seen_keys = set()
    for kind in ("bilingual", "english_only", "derived", "see_also", "poly"):
        cand = [r for r in typed[kind] if r["key"] not in seen_keys]
        rng.shuffle(cand)
        for row in cand[:2]:
            picked.append({**row, "sample_type": kind, "review": "auto_structure"})
            seen_keys.add(row["key"])
    leftover = [r for r in pool if r["key"] not in seen_keys]
    rng.shuffle(leftover)
    for row in leftover:
        if len(picked) >= 20:
            break
        picked.append({**row, "sample_type": "letter_bucket", "review": "auto_structure"})
        seen_keys.add(row["key"])
    (out_dir / "random_sample.json").write_text(json.dumps(picked, ensure_ascii=False, indent=2), encoding="utf-8")

    stats_path = out_dir / "stats.json"
    timing = {
        "elapsed_sec": round(elapsed, 3),
        "peak_rss_bytes": rss_peak,
        "peak_rss_mib": None if rss_peak is None else round(rss_peak / (1024 * 1024), 1),
        "reader": {
            "records_declared": reader_report.records,
            "encoding_fffd_sampled": reader_report.encoding_fffd_sampled,
            "sampled_blocks": reader_report.sampled_blocks,
            "sampled_bytes": reader_report.sampled_bytes,
            "record_block_types": reader_report.record_block_type_counts,
            "decode_policy": reader_report.decode_policy,
            "lzo_available": reader_report.lzo_available,
        },
    }
    stats_path.write_text(
        json.dumps({"counts": counts, "timing": timing, "reader_notes": reader_report.notes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in files:
            zf.write(unpacked / name, arcname=name)

    bump_rss()
    return {
        "pack": str(zip_path),
        "unpacked": str(unpacked),
        "counts": counts,
        "timing": timing,
        "mdx_sha256": reader_report.sha256,
    }
