"""Read-only dictionary audit; samples and metadata only, no product conversion."""
import importlib
import json
from pathlib import Path
import re
import sys
import types
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '电子词典/电脑版~朗文当代第六版英汉'
OUT = Path(__file__).resolve().parent
# readmdict 0.1.1's package initializer unconditionally requires optional LZO.
# Load its implementation directly: v2 zlib files do not require LZO.
reader_path = next((ROOT / 'tmp/mdx-audit-uv-cache/archive-v0').glob('*/readmdict/readmdict.py')).parent
pkg = types.ModuleType('audit_readmdict')
pkg.__path__ = [str(reader_path)]
sys.modules[pkg.__name__] = pkg
reader = importlib.import_module('audit_readmdict.readmdict')
from bs4 import BeautifulSoup

TARGETS = '''run|set|bank|light|throughout|resonate|subtle|yield|running|studies|went|better|children|indices|propagation|refraction|metasurface|wavefront|evanescent|anisotropic|eigenvalue|discontinuity|run out of|in terms of|as a result|take into account|resonate with|phase shift|browser|blockchain|chatbot|embeddings|point|fish|cold|almighty|account'''.split('|')
mdx = reader.MDX(str(next(SOURCE.glob('*.mdx'))))
print('MDX indexed:', len(mdx), flush=True)
samples = {}
stats = Counter()
untranslated = []
for rawkey, rawvalue in mdx.items():
    key, value = rawkey.decode('utf-8'), rawvalue.decode('utf-8')
    stats['records'] += 1
    stats['decoded_utf8_bytes'] += len(rawvalue)
    redirect = value.strip().startswith('@@@LINK=')
    stats['redirects' if redirect else 'non_redirects'] += 1
    if not redirect:
        if re.search(r'[\u4e00-\u9fff]', value):
            stats['non_redirects_with_chinese'] += 1
        else:
            stats['non_redirects_without_chinese'] += 1
            untranslated.append(key)
        if re.search(r'<tran\b', value, re.I):
            stats['non_redirects_with_tran_tag'] += 1
    for label, pattern in [('has_chinese', r'[\u4e00-\u9fff]'), ('has_script_tag', r'<script\b'), ('has_replacement_char', '\ufffd'), ('has_private_use_char', r'[\ue000-\uf8ff]')]:
        if re.search(pattern, value, re.I):
            stats[label] += 1
    if key.casefold() in TARGETS:
        samples.setdefault(key, []).append(value)
assert stats['records'] == len(mdx), 'Incomplete iteration'
(OUT / 'samples.raw.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding='utf-8')
summary = {}
for key, entries in samples.items():
    summary[key] = []
    for value in entries:
        soup = BeautifulSoup(value, 'html.parser')
        classes = Counter(c for tag in soup.find_all(True) for c in tag.get('class', []))
        summary[key].append({'chars': len(value), 'classes': dict(classes), 'text_start': soup.get_text(' ', strip=True)[:1800], 'scripts': [x.get('src', '(inline)') for x in soup.find_all('script')], 'ipa': [x.get_text(' ', strip=True) for x in soup.select('.pron, .amepron, .brepron')], 'resource_examples': [x.get('src') for x in soup.select('[src]')][:8]})
mdd = reader.MDD(str(next(SOURCE.glob('*.mdd'))))
resource_keys = [k.decode('utf-8') for k in mdd.keys()]
extensions = Counter(Path(k).suffix.lower() for k in resource_keys)
# Inspect record sizes from block metadata without unpacking the resource archive.
with open(mdd._fname, 'rb') as f:
    f.seek(mdd._record_block_offset)
    blocks, entries, info_size, compressed = [mdd._read_number(f) for _ in range(4)]
    block_info = [(mdd._read_number(f), mdd._read_number(f)) for _ in range(blocks)]
total_uncompressed = sum(x[1] for x in block_info)
sizes_by_ext = Counter()
for i, (start, rawkey) in enumerate(mdd._key_list):
    end = mdd._key_list[i + 1][0] if i + 1 < len(mdd._key_list) else total_uncompressed
    sizes_by_ext[Path(rawkey.decode('utf-8')).suffix.lower()] += end - start
result = {'source': str(SOURCE), 'files_bytes': {p.name:p.stat().st_size for p in SOURCE.iterdir() if p.is_file()}, 'header': {k.decode():v.decode() for k,v in mdx.header.items()}, 'stats':dict(stats), 'queries': TARGETS, 'exact_hits': [t for t in TARGETS if any(k.casefold()==t for k in samples)], 'exact_misses': [t for t in TARGETS if not any(k.casefold()==t for k in samples)], 'samples':summary, 'mdd': {'resources':len(mdd), 'extensions':dict(extensions), 'uncompressed_bytes_by_extension':dict(sizes_by_ext), 'first_keys':resource_keys[:20], 'js_css_font_keys':[k for k in resource_keys if Path(k).suffix.lower() in ['.js','.css','.ttf','.woff','.woff2','.otf']]}}
(OUT / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'resource-keys.json').write_text(json.dumps(resource_keys, ensure_ascii=False), encoding='utf-8')
(OUT / 'entries-without-chinese.json').write_text(json.dumps(untranslated, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['samples','mdd']}, ensure_ascii=False, indent=2))
print(json.dumps(result['mdd'], ensure_ascii=False, indent=2))
