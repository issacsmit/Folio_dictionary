"""Check actual definition nodes for bilingual pairing; no source modifications."""
import importlib
import json
from pathlib import Path
import re
import sys
import types
from collections import Counter
from lxml import html

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
package = types.ModuleType('audit_readmdict')
package.__path__ = [str(next((ROOT/'tmp/mdx-audit-uv-cache/archive-v0').glob('*/readmdict/readmdict.py')).parent)]
sys.modules[package.__name__] = package
MDX = importlib.import_module('audit_readmdict.readmdict').MDX
mdx = MDX(str(next((ROOT/'电子词典/电脑版~朗文当代第六版英汉').glob('*.mdx'))))
definition_nodes = html.etree.XPath('//*[contains(concat(" ", normalize-space(@class), " "), " def ")]')
counts = Counter()
exceptions = []
mixed = []
no_defs = []
for key_bytes, value_bytes in mdx.items():
    counts['records'] += 1
    value = value_bytes.decode('utf-8')
    if value.strip().startswith('@@@LINK='):
        continue
    counts['non_redirects'] += 1
    key = key_bytes.decode('utf-8')
    root = html.fromstring(value)
    defs = definition_nodes(root)
    local = Counter()
    for node in defs:
        counts['definition_nodes'] += 1
        trans = node.xpath('.//tran')
        ens = node.xpath('.//en')
        chinese = [' '.join(t.itertext()).strip() for t in trans]
        english = [' '.join(e.itertext()).strip() for e in ens]
        if any(re.search('[\u4e00-\u9fff]',t) for t in chinese):
            counts['chinese_definition_nodes'] += 1
            local['chinese_defs'] += 1
            if any(re.search('[A-Za-z]',e) for e in english):
                counts['chinese_definition_nodes_with_english_en'] += 1
            else:
                counts['chinese_definition_nodes_without_english_en'] += 1
                exceptions.append({'key':key,'html':html.tostring(node,encoding='unicode')[:1800]})
        elif not trans and re.search('[A-Za-z]',' '.join(node.itertext())):
            local['english_only_defs'] += 1
    if local['chinese_defs']:
        counts['records_with_chinese_defs'] += 1
        if local['english_only_defs']:
            counts['records_with_chinese_and_english_only_defs'] += 1
            if len(mixed)<20:
                mixed.append({'key':key,**local})
    if not defs:
        counts['records_without_def_nodes'] += 1
        if len(no_defs)<20:
            no_defs.append(key)
result={'method':'Check .def descendant tran containing CJK against nonempty en containing Latin letters. All def modules included; detects structural pairing, not semantic accuracy or full dictionary completeness. English-only auxiliary modules may coexist with bilingual primary senses.', 'counts':dict(counts),'exceptions':exceptions,'mixed_module_examples':mixed,'without_def_examples':no_defs}
(OUT/'bilingual-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
