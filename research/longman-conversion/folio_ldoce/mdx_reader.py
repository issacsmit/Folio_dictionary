"""Read MDict 2.0 MDX without executing dictionary scripts.

Uses the existing readmdict implementation (GPL-3 in the module source; the
PyPI wrapper metadata claims MIT). The package __init__ requires optional LZO,
which this v2 zlib dictionary does not need, so the reader is imported from
readmdict.py directly.

readmdict decodes record bytes with errors='ignore'. That is not treated as a
proof of lossless encoding. This module adds count, checksum, and sampled
strict-decode checks against decompressed record blocks.
"""
from __future__ import annotations

import hashlib
import importlib
import sys
import types
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from struct import unpack

from .paths import READMDICT_CACHE, SOURCE_DIR


def _load_readmdict_module():
    candidates = list(READMDICT_CACHE.glob("*/readmdict/readmdict.py"))
    if not candidates:
        import readmdict as pkg  # type: ignore

        path = Path(pkg.__file__).resolve().parent / "readmdict.py"
        candidates = [path]
    reader_path = candidates[0].parent
    pkg = types.ModuleType("folio_readmdict_gpl")
    pkg.__path__ = [str(reader_path)]
    sys.modules[pkg.__name__] = pkg
    return importlib.import_module("folio_readmdict_gpl.readmdict")


_READER = None


def reader_module():
    global _READER
    if _READER is None:
        _READER = _load_readmdict_module()
    return _READER


def default_mdx_path() -> Path:
    matches = list(SOURCE_DIR.glob("*.mdx"))
    if not matches:
        raise FileNotFoundError(f"No MDX in {SOURCE_DIR}")
    return matches[0]


@dataclass
class ReaderReport:
    path: str
    records: int
    header: dict
    sha256: str
    file_bytes: int
    encoding_fffd_sampled: int
    sampled_blocks: int
    sampled_bytes: int
    record_block_type_counts: dict
    lzo_available: bool
    decode_policy: str
    notes: list[str] = field(default_factory=list)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sample_block_encoding(mdx) -> tuple[int, int, int, dict]:
    """Decompress first/middle/last record blocks; count U+FFFD with errors='replace'.

    Full-block Adler-32 is asserted again inside readmdict.items(). This extra
    scan is an encoding check, not a second full dictionary parse.
    """
    type_counts: dict[str, int] = {}
    fffd = 0
    blocks = 0
    nbytes = 0
    encoding = (mdx._encoding or "UTF-8").replace("-", "").upper()
    codec = "utf-8" if encoding in {"UTF8", ""} else mdx._encoding
    with open(mdx._fname, "rb") as fh:
        fh.seek(mdx._record_block_offset)
        num_record_blocks = mdx._read_number(fh)
        _num_entries = mdx._read_number(fh)
        record_block_info_size = mdx._read_number(fh)
        _record_block_size = mdx._read_number(fh)
        infos = []
        info_bytes = 0
        for _ in range(num_record_blocks):
            compressed_size = mdx._read_number(fh)
            decompressed_size = mdx._read_number(fh)
            infos.append((compressed_size, decompressed_size))
            info_bytes += mdx._number_width * 2
        if info_bytes != record_block_info_size:
            raise RuntimeError("record block info size mismatch")
        if not infos:
            return 0, 0, 0, {}
        pick = {0, len(infos) // 2, len(infos) - 1}
        lzo = reader_module().lzo
        for idx, (compressed_size, decompressed_size) in enumerate(infos):
            blob = fh.read(compressed_size)
            kind = blob[:4]
            key = {b"\x00\x00\x00\x00": "none", b"\x01\x00\x00\x00": "lzo", b"\x02\x00\x00\x00": "zlib"}.get(kind, kind.hex())
            type_counts[key] = type_counts.get(key, 0) + 1
            if idx not in pick:
                continue
            adler32 = unpack(">I", blob[4:8])[0]
            if kind == b"\x00\x00\x00\x00":
                data = blob[8:]
            elif kind == b"\x01\x00\x00\x00":
                if lzo is None:
                    raise RuntimeError("record block uses LZO but python-lzo is not available")
                header = b"\xf0" + decompressed_size.to_bytes(4, "big")
                data = lzo.decompress(header + blob[8:])
            elif kind == b"\x02\x00\x00\x00":
                data = zlib.decompress(blob[8:])
            else:
                raise RuntimeError(f"unknown record block type {kind!r}")
            if (zlib.adler32(data) & 0xFFFFFFFF) != adler32:
                raise RuntimeError("record block Adler-32 mismatch")
            if len(data) != decompressed_size:
                raise RuntimeError("record block decompressed size mismatch")
            text = data.decode(codec, errors="replace")
            fffd += text.count("\ufffd")
            nbytes += len(data)
            blocks += 1
    return fffd, blocks, nbytes, type_counts


def open_mdx(path: Path | None = None):
    path = path or default_mdx_path()
    mdx = reader_module().MDX(str(path))
    return mdx, path


def inspect_reader(mdx, path: Path) -> ReaderReport:
    header = {}
    for key, value in mdx.header.items():
        k = key.decode("utf-8", "replace") if isinstance(key, bytes) else str(key)
        v = value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
        header[k] = v
    fffd, blocks, nbytes, types = _sample_block_encoding(mdx)
    notes = [
        "readmdict.items() still decodes each record with errors='ignore' before yield.",
        "This report's encoding_fffd_sampled uses errors='replace' on first/middle/last decompressed blocks.",
        "Library Adler-32 checks run while iterating items().",
    ]
    if fffd:
        notes.append(f"Replacement characters found in sampled/full block decode: {fffd}")
    return ReaderReport(
        path=str(path),
        records=len(mdx),
        header=header,
        sha256=file_sha256(path),
        file_bytes=path.stat().st_size,
        encoding_fffd_sampled=fffd,
        sampled_blocks=blocks,
        sampled_bytes=nbytes,
        record_block_type_counts=types,
        lzo_available=reader_module().lzo is not None,
        decode_policy="readmdict items() errors=ignore; integrity scan errors=replace on first/middle/last blocks",
        notes=notes,
    )


def iter_records(mdx):
    """Yield (key, value, is_link, link_target) as Unicode strings."""
    for raw_key, raw_val in mdx.items():
        if isinstance(raw_key, bytes):
            key = raw_key.decode("utf-8")
        else:
            key = str(raw_key)
        if isinstance(raw_val, bytes):
            value = raw_val.decode("utf-8")
        else:
            value = str(raw_val)
        stripped = value.lstrip("\ufeff").strip()
        if stripped.startswith("@@@LINK="):
            yield key, value, True, stripped[8:].strip()
        else:
            yield key, value, False, None
