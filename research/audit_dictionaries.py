"""Research only: download public datasets into temporary storage and audit 32 queries.

No extension code or persistent dictionary installation. Output contains aggregate
metrics and only the selected research entries. Python standard library only.
"""
import concurrent.futures
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import urllib.request
from urllib.parse import quote
import xml.etree.ElementTree as ET

GROUPS = {
    "everyday": "run|set|bank|light|throughout|resonate|subtle|yield".split("|"),
    "inflections": "running|studies|went|better|children|indices".split("|"),
    "academic": "propagation|refraction|metasurface|wavefront|evanescent|anisotropic|eigenvalue|discontinuity".split("|"),
    "phrases": "run out of|in terms of|as a result|take into account|resonate with|phase shift".split("|"),
    "technology": "browser|blockchain|chatbot|embeddings".split("|"),
}
QUERIES = {q for group in GROUPS.values() for q in group}
SOURCES = {
    "ecdict": "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv",
    "freedict": "https://download.freedict.org/dictionaries/eng-zho/2025.11.23/freedict-eng-zho-2025.11.23.src.tar.xz",
    "kaikki_traditional_label": "https://kaikki.org/zhwiktionary/英語/kaikki.org-dictionary-英語.jsonl",
    "kaikki_simplified_label": "https://kaikki.org/zhwiktionary/英语/kaikki.org-dictionary-英语.jsonl",
}


def inspect(name, url):
    print("Fetching", name, flush=True)
    result = {"url": url, "samples": {}, "rows": 0}
    digest = hashlib.sha256()
    with tempfile.TemporaryFile() as data:
        req = urllib.request.Request(quote(url, safe=":/%"), headers={"User-Agent": "DictionaryResearch/1.0"})
        with urllib.request.urlopen(req, timeout=90) as response:
            result["last_modified"] = response.headers.get("Last-Modified")
            while chunk := response.read(1024 * 1024):
                data.write(chunk)
                digest.update(chunk)
        result["download_bytes"] = data.tell()
        result["sha256"] = digest.hexdigest()
        data.seek(0)
        words, pronunciations, definitions = set(), set(), set()
        if name == "ecdict":
            reader = csv.DictReader(io.TextIOWrapper(data, encoding="utf-8-sig", newline=""))
            result["fields"] = reader.fieldnames
            result["nonempty_fields"] = dict.fromkeys(reader.fieldnames, 0)
            for row in reader:
                result["rows"] += 1
                word = row["word"].casefold()
                words.add(word)
                for field, value in row.items():
                    if value:
                        result["nonempty_fields"][field] += 1
                if row.get("phonetic"):
                    pronunciations.add(word)
                if row.get("translation"):
                    definitions.add(word)
                if word in QUERIES:
                    result["samples"].setdefault(word, []).append(row)
        elif name == "freedict":
            ns = {"t": "http://www.tei-c.org/ns/1.0"}
            with tarfile.open(fileobj=data, mode="r:xz") as archive:
                result["members"] = [{"name": m.name, "bytes": m.size} for m in archive.getmembers() if m.isfile()]
                member = next(m for m in archive.getmembers() if m.name.endswith(".tei"))
                result["tei_bytes"] = member.size
                with archive.extractfile(member) as source:
                    root = ET.parse(source).getroot()
                result["header"] = ET.tostring(root.find("t:teiHeader", ns), encoding="unicode")
                for entry in root.findall(".//t:entry", ns):
                    result["rows"] += 1
                    keys = [e.text.casefold() for e in entry.findall("t:form/t:orth", ns) if e.text]
                    words.update(keys)
                    if entry.findall(".//t:pron", ns):
                        pronunciations.update(keys)
                    if entry.findall(".//t:cit[@type='trans']/t:quote", ns):
                        definitions.update(keys)
                    for word in set(keys) & QUERIES:
                        result["samples"].setdefault(word, []).append(ET.tostring(entry, encoding="unicode"))
        else:
            for line in data:
                row = json.loads(line)
                result["rows"] += 1
                word = row["word"].casefold()
                words.add(word)
                if any(s.get("ipa") for s in row.get("sounds", [])):
                    pronunciations.add(word)
                if any(s.get("glosses") for s in row.get("senses", [])):
                    definitions.add(word)
                if word in QUERIES:
                    # Do not retain quoted examples, media URLs, or unrelated metadata.
                    sample = {k: row[k] for k in ("word", "lang", "lang_code", "pos", "forms") if k in row}
                    sample["sounds"] = [{k: sound[k] for k in ("ipa", "tags", "raw_tags") if k in sound}
                                        for sound in row.get("sounds", []) if sound.get("ipa")]
                    sample["senses"] = [{k: sense[k] for k in ("glosses", "tags", "form_of") if k in sense}
                                        for sense in row.get("senses", [])]
                    result["samples"].setdefault(word, []).append(sample)
        result["distinct_casefold_words"] = len(words)
        result["words_with_pronunciation_field"] = len(pronunciations)
        result["words_with_translation_or_gloss_field"] = len(definitions)
    result["sample_hits_by_group"] = {
        group: {"hits": [q for q in queries if q in result["samples"]],
                "missing": [q for q in queries if q not in result["samples"]]}
        for group, queries in GROUPS.items()
    }
    print("Finished", name, result["download_bytes"], "bytes", flush=True)
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    output = {"audit_date": "2026-09-20", "groups": GROUPS, "method": "Casefold exact headword lookup; no stemming, lemmatization, or quality scoring. Kaikki uses deprecated website export for this snapshot audit only.", "sources": {}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(inspect, name, url): name for name, url in SOURCES.items()}
        for job in concurrent.futures.as_completed(jobs):
            name = jobs[job]
            try:
                output["sources"][name] = job.result()
            except Exception as exc:
                output["sources"][name] = {"url": SOURCES[name], "error": str(exc)}
    destination = Path(__file__).with_name("dictionary-audit-results.json")
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, result in output["sources"].items():
        print(name, json.dumps({k: v for k, v in result.items() if k not in {"samples", "header", "members"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
