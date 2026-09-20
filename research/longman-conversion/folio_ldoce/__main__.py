from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .convert import convert
from .paths import PACK_ZIP, UNPACKED_DIR
from .query import query
from .validate import ledger_stats, validate_unpacked, validate_zip
from .verify import verify_pack


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="folio_ldoce", description="Longman MDX → Folio pack")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_conv = sub.add_parser("convert", help="Convert the full MDX into a dictionary pack")
    p_conv.add_argument("--mdx", type=Path, default=None)
    p_conv.add_argument("--out", type=Path, default=None)
    p_conv.add_argument("--limit", type=int, default=None, help="Debug: stop after N MDX records")

    p_val = sub.add_parser("validate", help="Validate unpacked files and zip")
    p_val.add_argument("--unpacked", type=Path, default=UNPACKED_DIR)
    p_val.add_argument("--zip", type=Path, default=PACK_ZIP)

    p_q = sub.add_parser("query", help="Look up a word in the pack")
    p_q.add_argument("text")
    p_q.add_argument("--pack", type=Path, default=PACK_ZIP)
    p_q.add_argument("--limit", type=int, default=8)

    p_ver = sub.add_parser("verify", help="Required-word structural checks against the pack")
    p_ver.add_argument("--pack", type=Path, default=PACK_ZIP)

    args = parser.parse_args(argv)
    if args.cmd == "convert":
        result = convert(mdx_path=args.mdx, out_dir=args.out, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "validate":
        u = validate_unpacked(args.unpacked)
        z = validate_zip(args.zip)
        led = ledger_stats()
        print(json.dumps({"unpacked": u, "zip": z, "ledger": led}, ensure_ascii=False, indent=2))
        return 0 if u.get("ok") and z.get("ok") else 1
    if args.cmd == "query":
        print(query(args.text, pack=args.pack, limit=args.limit))
        return 0
    if args.cmd == "verify":
        result = verify_pack(pack=args.pack)
        print(json.dumps({"automatic_ok": result["automatic_ok"], "checks": result["automatic_checks"], "counts": result["manifest_counts"]}, ensure_ascii=False, indent=2))
        return 0 if result["automatic_ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
