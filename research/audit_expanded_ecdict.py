"""Research audit of the official stardict.7z archive; needs system tar with 7z support.
Usage: python audit_expanded_ecdict.py PATH_TO_STARDICT_7Z
Reads archive data through stdout without extracting files or installing a dictionary.
"""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from audit_dictionaries import GROUPS, QUERIES


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    archive = Path(sys.argv[1])
    result = {"url": "https://raw.githubusercontent.com/skywind3000/ECDICT/master/stardict.7z",
              "audit_date": "2026-09-20", "download_bytes": archive.stat().st_size,
              "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "rows": 0, "samples": {}, "uncompressed_bytes": 0}
    digest = hashlib.sha256()
    def lines(stream):
        for line in stream:
            digest.update(line)
            result["uncompressed_bytes"] += len(line)
            yield line.decode("utf-8-sig")
    process = subprocess.Popen(["tar", "-xOf", str(archive), "stardict.csv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    reader = csv.DictReader(lines(process.stdout))
    result["fields"] = reader.fieldnames
    result["nonempty_fields"] = dict.fromkeys(reader.fieldnames, 0)
    for row in reader:
        result["rows"] += 1
        for field, value in row.items():
            if value:
                result["nonempty_fields"][field] += 1
        word = row["word"].casefold()
        if word in QUERIES:
            result["samples"].setdefault(word, []).append(row)
    error = process.stderr.read().decode(errors="replace")
    if process.wait() != 0:
        raise RuntimeError(error)
    result["uncompressed_sha256"] = digest.hexdigest()
    result["sample_hits_by_group"] = {group: {"hits": [q for q in queries if q in result["samples"]],
                                                 "missing": [q for q in queries if q not in result["samples"]]}
                                        for group, queries in GROUPS.items()}
    Path(__file__).with_name("expanded-ecdict-audit-results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "samples"}, ensure_ascii=False))
    for q in ("run", "throughout", "resonate", "metasurface", "blockchain", "chatbot", "embeddings", "resonate with"):
        print(q, json.dumps(result["samples"].get(q),ensure_ascii=False))


if __name__ == "__main__":
    main()
