"""Validate pack schema, IDs, lookup/parent references, and ZIP integrity."""
from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from .paths import OUTPUT_DIR, PACK_ZIP
from .schema import ENTRY_SCHEMA, LOOKUP_SCHEMA, MANIFEST_SCHEMA


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_jsonl_bytes(data: bytes):
    text = data.decode("utf-8")
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


def _sense_ids(entry: dict) -> set[str]:
    ids: set[str] = set()

    def walk(senses):
        for sense in senses or []:
            sid = sense.get("id")
            if sid:
                ids.add(sid)
            walk(sense.get("senses") or [])

    for group in entry.get("pos_groups") or []:
        walk(group.get("senses") or [])
    return ids


def validate_members(members: dict[str, bytes]) -> dict:
    """Validate an in-memory dictionary pack. Does not read UNPACKED_DIR."""
    errors: list[str] = []
    required = ("manifest.json", "entries.jsonl", "lookup.jsonl")
    missing = [name for name in required if name not in members]
    if missing:
        return {
            "ok": False,
            "errors": [f"missing members {missing}"],
            "error_count": 1,
            "entries": 0,
            "lookup_keys": 0,
            "missing_refs": 0,
            "duplicate_ids": 0,
            "missing_sense_refs": 0,
            "missing_parent_refs": 0,
        }

    try:
        manifest = json.loads(members["manifest.json"].decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "errors": [f"manifest json: {exc}"], "error_count": 1}

    for err in Draft202012Validator(MANIFEST_SCHEMA).iter_errors(manifest):
        errors.append(f"manifest: {err.message}")

    checksums = manifest.get("checksums") or {}
    for name in ("entries.jsonl", "lookup.jsonl"):
        expected = checksums.get(name)
        if not expected:
            errors.append(f"manifest missing checksum for {name}")
            continue
        actual = _sha256_bytes(members[name])
        if actual != expected:
            errors.append(f"checksum mismatch {name}: manifest {expected} != {actual}")

    entry_validator = Draft202012Validator(ENTRY_SCHEMA)
    lookup_validator = Draft202012Validator(LOOKUP_SCHEMA)
    ids: set[str] = set()
    dup_ids: list[str] = []
    sense_index: dict[str, set[str]] = {}
    parents: list[tuple[str, str]] = []
    n_entries = 0
    for row in _load_jsonl_bytes(members["entries.jsonl"]):
        n_entries += 1
        for err in entry_validator.iter_errors(row):
            errors.append(f"entry {row.get('id')}: {err.message}")
            break
        eid = row.get("id")
        if eid in ids:
            dup_ids.append(eid)
        ids.add(eid)
        sense_index[eid] = _sense_ids(row)
        parent = row.get("parent") or {}
        pid = parent.get("id") if isinstance(parent, dict) else None
        if pid:
            parents.append((eid, pid))

    n_lookup = 0
    missing_refs = 0
    missing_sense_refs = 0
    lookup_norms: set[str] = set()
    for row in _load_jsonl_bytes(members["lookup.jsonl"]):
        n_lookup += 1
        for err in lookup_validator.iter_errors(row):
            errors.append(f"lookup {row.get('norm')}: {err.message}")
            break
        norm = row.get("norm")
        if norm in lookup_norms:
            errors.append(f"duplicate lookup norm {norm}")
        lookup_norms.add(norm)
        for match in row.get("matches") or []:
            eid = match.get("entry_id")
            if eid not in ids:
                missing_refs += 1
                if missing_refs <= 20:
                    errors.append(f"lookup {norm} missing entry {eid}")
                continue
            sid = match.get("sense_id")
            if sid:
                if sid not in sense_index.get(eid, set()):
                    missing_sense_refs += 1
                    if missing_sense_refs <= 20:
                        errors.append(f"lookup {norm} sense {sid} not in entry {eid}")

    missing_parent_refs = 0
    for eid, pid in parents:
        if pid not in ids:
            missing_parent_refs += 1
            if missing_parent_refs <= 20:
                errors.append(f"entry {eid} parent.id missing {pid}")

    if dup_ids:
        errors.append(f"duplicate entry ids: {dup_ids[:10]} count={len(dup_ids)}")
    counts = manifest.get("counts") or {}
    if n_entries != counts.get("entries"):
        errors.append(f"manifest entries {counts.get('entries')} != file {n_entries}")
    if n_lookup != counts.get("lookup_keys"):
        errors.append(f"manifest lookup_keys {counts.get('lookup_keys')} != file {n_lookup}")

    return {
        "ok": not errors,
        "errors": errors[:80],
        "error_count": len(errors),
        "entries": n_entries,
        "lookup_keys": n_lookup,
        "missing_refs": missing_refs,
        "missing_sense_refs": missing_sense_refs,
        "missing_parent_refs": missing_parent_refs,
        "duplicate_ids": len(dup_ids),
    }


def validate_unpacked(root: Path) -> dict:
    members = {}
    for name in ("manifest.json", "entries.jsonl", "lookup.jsonl"):
        path = root / name
        if path.is_file():
            members[name] = path.read_bytes()
    return validate_members(members)


def validate_zip(zip_path: Path | None = None) -> dict:
    """Validate the ZIP's own members. Does not read output/unpacked."""
    zip_path = zip_path or PACK_ZIP
    if not zip_path.is_file():
        return {"ok": False, "errors": [f"missing zip {zip_path}"]}
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        required = {"manifest.json", "entries.jsonl", "lookup.jsonl"}
        missing = sorted(required - names)
        info = {n: zf.getinfo(n).file_size for n in required if n in names}
        bad = zf.testzip()
        members = {n: zf.read(n) for n in required if n in names}
    unpacked = validate_members(members)
    errors = list(unpacked.get("errors") or [])
    if missing:
        errors.append(f"zip missing {missing}")
    if bad:
        errors.append(f"zip corrupt member {bad}")
    return {
        "ok": not errors,
        "errors": errors[:80],
        "error_count": len(errors),
        "zip_bytes": zip_path.stat().st_size,
        "zip_members": info,
        **{k: v for k, v in unpacked.items() if k not in {"ok", "errors", "error_count"}},
    }


def ledger_stats(ledger_path: Path | None = None) -> dict:
    path = ledger_path or (OUTPUT_DIR / "ledger.jsonl")
    counts = Counter()
    n = 0
    for row in _load_jsonl(path):
        n += 1
        counts[row.get("status") or "unknown"] += 1
    return {"rows": n, "by_status": dict(counts)}
