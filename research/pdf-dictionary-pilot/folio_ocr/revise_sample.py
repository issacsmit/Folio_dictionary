"""Apply page-evidence revisions to a fixed 30-entry sample. Does not invent IPA."""

from __future__ import annotations

import json
from pathlib import Path

from .config import OUTPUT_DIR

# Corrections taken from the printed sample pages, not from memory of other editions.
PATCHES = {
    "p0100-c0-y0279-018": {  # ally n
        "senses": [
            {"sense_no": "1", "labels": ["[C]"], "definition_en": None, "definition_zh": "同盟国"},
            {"sense_no": "2", "labels": [], "definition_en": None, "definition_zh": "（两次世界大战中的）同盟国；协约国"},
            {"sense_no": "3", "labels": [], "definition_en": None, "definition_zh": "盟友，支持者"},
            {"sense_no": "4", "labels": [], "definition_en": None, "definition_zh": "辅助物"},
        ],
        "collocations": [
            {
                "phrase_display": "a staunch ally",
                "phrase_key": "a staunch ally",
                "explanation_zh": "坚定的支持者",
                "source": "revision",
                "labels": [],
            },
            {
                "phrase_display": "a network of political allies",
                "phrase_key": "a network of political allies",
                "explanation_zh": "政治盟友网",
                "source": "revision",
                "labels": [],
            },
        ],
        "ipa_uncertain": True,
        "notes": "page 100 left; dropped example sentences used as collocations",
    },
    "p0100-c0-y1436-019": {  # ally v
        "headword_display": "ally",
        "senses": [
            {"sense_no": "1", "labels": ["[T]", "always +adv/prep"], "definition_en": None, "definition_zh": "与…结盟"},
        ],
        "collocations": [
            {
                "phrase_display": "ally yourself to/with sb",
                "phrase_key": "ally yourself to with sb",
                "explanation_zh": "与某人结盟",
                "source": "revision",
                "labels": [],
            }
        ],
        "ipa_uncertain": True,
    },
    "p0100-c0-y1842-020": {  # alma mater
        "senses": [
            {"sense_no": "1", "labels": ["[singular]"], "definition_en": None, "definition_zh": "母校"},
            {"sense_no": "2", "labels": ["AmE", "【美】"], "definition_en": None, "definition_zh": "校歌"},
        ],
        "collocations": [],
        "ipa_uncertain": True,
        "notes": "page 100; removed almanac lines wrongly merged here",
    },
    "p0100-c0-y3283-022": {"ipa_uncertain": True},  # almond 扁桃仁；扁桃树 already ok
    "p0100-c0-y3633-023": {  # almost
        "senses": [
            {"sense_no": "1", "labels": ["adv"], "definition_en": None, "definition_zh": "几乎，差不多"},
        ],
        "collocations": [
            {
                "phrase_display": "almost all/every/everything",
                "phrase_key": "almost all every everything",
                "explanation_zh": "几乎全部/每一个/一切",
                "source": "revision",
                "labels": [],
            }
        ],
        "ipa_uncertain": True,
        "notes": "page 100; examples removed from collocation list",
    },
    "p0100-c1-y4382-024": {  # alms
        "senses": [
            {
                "sense_no": "1",
                "labels": ["[plural]", "literary", "【文】"],
                "definition_en": None,
                "definition_zh": "（旧时的）施舍物，救济品",
            }
        ],
        "ipa_uncertain": True,
    },
    "p0100-c1-y4590-025": {"ipa_uncertain": True},  # almshouse
    "p0100-c1-y4862-026": {"ipa_uncertain": True},  # aloe vera
    "p0100-c0-y2468-021": {  # almighty, OCR headword alomightoy
        "headword_display": "almighty",
        "headword_key": "almighty",
        "ipa_uncertain": True,
        "notes": "page 100 highlight bar; OCR headword was alomightoy; Chinese senses kept from page",
    },
    "p0104-c1-y0695-071": {"ipa_uncertain": True},  # alto n
    "p0499-c0-y0328-017": {  # cold adj
        "senses": [
            {"sense_no": "1", "labels": [], "definition_en": None, "definition_zh": "冷的，寒冷的，冰凉的"},
            {"sense_no": "2", "labels": [], "definition_en": None, "definition_zh": "（天气）寒冷的"},
        ],
        "ipa_uncertain": True,
        "notes": "page 499; auto senses were usage-box titles, replaced from main gloss",
    },
    "p0500-c0-y2234-020": {  # cold n
        "senses": [
            {"sense_no": "1", "labels": ["[C]"], "definition_en": None, "definition_zh": "感冒，伤风"},
            {"sense_no": "2", "labels": ["[U]"], "definition_en": None, "definition_zh": "冷，寒冷"},
        ],
        "collocations": [
            {
                "phrase_display": "have (got) a cold",
                "phrase_key": "have a cold",
                "explanation_zh": "得了感冒",
                "source": "revision",
                "labels": [],
            },
            {
                "phrase_display": "catch a cold",
                "phrase_key": "catch a cold",
                "explanation_zh": "患感冒",
                "source": "revision",
                "labels": [],
            },
            {
                "phrase_display": "a streaming cold",
                "phrase_key": "a streaming cold",
                "explanation_zh": "感冒流鼻涕",
                "source": "revision",
                "labels": ["BrE", "【英】"],
            },
        ],
        "ipa_uncertain": True,
    },
    "p0500-c1-y0790-022": {  # cold adv
        "senses": [
            {"sense_no": "1", "labels": ["AmE", "【美】"], "definition_en": None, "definition_zh": "突然，贸然；完全地，彻底地"},
            {"sense_no": "2", "labels": ["informal", "【非正式】"], "definition_en": None, "definition_zh": "不省人事"},
        ],
        "collocations": [
            {
                "phrase_display": "out cold",
                "phrase_key": "out cold",
                "explanation_zh": "不省人事",
                "source": "revision",
                "labels": ["informal"],
            }
        ],
        "ipa_uncertain": True,
    },
    "p0500-c1-y1338-023": {  # cold-blooded
        "senses": [
            {"sense_no": "1", "labels": ["adj"], "definition_en": None, "definition_zh": "残酷的，无情的，冷血的"},
            {"sense_no": "2", "labels": [], "definition_en": None, "definition_zh": "（动物）冷血的"},
        ],
        "ipa_uncertain": True,
        "notes": "page 500; dropped fusion/front junk merged into sense 2",
    },
    "p0500-c1-y4302-026": {"ipa_uncertain": True},
    "p0500-c1-y4708-027": {"ipa_uncertain": True},
    "p0501-c0-y2090-031": {  # cold war
        "senses": [
            {"sense_no": "1", "labels": ["[singular]"], "definition_en": None, "definition_zh": "冷战"},
        ],
        "ipa_uncertain": True,
    },
    "p0501-c0-y2630-032": {"ipa_uncertain": True},
    "p1000-c0-y0468-027": {"ipa_uncertain": True},
    "p1000-c0-y2484-033": {"ipa_uncertain": True},
    "p1000-c1-y3289-044": {  # fish
        "senses": [
            {"sense_no": "1", "labels": ["[C]"], "definition_en": None, "definition_zh": "鱼"},
            {"sense_no": "2", "labels": ["[U]"], "definition_en": None, "definition_zh": "鱼肉"},
            {
                "sense_no": "3",
                "labels": [],
                "definition_en": None,
                "definition_zh": "如离水之鱼；（感到）生疏、不自在",
            },
        ],
        "collocations": [
            {
                "phrase_display": "like a fish out of water",
                "phrase_key": "like a fish out of water",
                "explanation_zh": "如离水之鱼；感到生疏、不自在",
                "source": "revision",
                "labels": [],
            },
            {
                "phrase_display": "there are plenty more fish in the sea",
                "phrase_key": "there are plenty more fish in the sea",
                "explanation_zh": "海里的鱼有的是；天涯何处无芳草",
                "source": "revision",
                "labels": [],
            },
        ],
        "ipa_uncertain": True,
    },
    "p1002-c0-y0244-052": {"ipa_uncertain": True},
    "p1002-c0-y3937-062": {"ipa_uncertain": True},
    "p1998-c1-y0592-014": {  # point n — do not keep verb senses
        "pos": "n",
        "senses": [
            {"sense_no": "1", "labels": ["[C]"], "definition_en": None, "definition_zh": "想法，观点"},
            {"sense_no": "2", "labels": [], "definition_en": None, "definition_zh": "要点，核心意思"},
            {"sense_no": "3", "labels": ["[U]"], "definition_en": None, "definition_zh": "目的，意义"},
            {"sense_no": "4", "labels": ["[C]"], "definition_en": None, "definition_zh": "地方，地点"},
            {"sense_no": "5", "labels": ["[C]"], "definition_en": None, "definition_zh": "时刻；阶段"},
        ],
        "collocations": [
            {
                "phrase_display": "there's no point in (doing) sth",
                "phrase_key": "there no point in doing sth",
                "explanation_zh": "做某事没有意义",
                "source": "revision",
                "labels": [],
            },
            {
                "phrase_display": "take sb's point",
                "phrase_key": "take sb point",
                "explanation_zh": "明白/同意某人的观点",
                "source": "revision",
                "labels": [],
            },
        ],
        "ipa_uncertain": True,
        "notes": "pages 1998-2000; removed verb senses that belong to point²",
    },
    "p2000-c1-y4308-017": {"ipa_uncertain": True},
    "p2002-c1-y1081-032": {"ipa_uncertain": True},
    "p2004-c0-y1254-056": {  # police
        "senses": [
            {"sense_no": "1", "labels": ["plural"], "definition_en": None, "definition_zh": "警察；警方"},
        ],
        "ipa_uncertain": True,
    },
    "p2001-c1-y3786-028": {"ipa_uncertain": True},
    "p2003-c1-y1011-048": {"ipa_uncertain": True},
    "p2003-c0-y1669-036": {"ipa_uncertain": True},
}


def apply() -> Path:
    auto = OUTPUT_DIR / "entries.auto.jsonl"
    out = OUTPUT_DIR / "entries.revised.jsonl"
    rows = []
    with auto.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    by_id = {r["id"]: r for r in rows}
    revised = []
    for eid, patch in PATCHES.items():
        if eid not in by_id:
            continue
        item = dict(by_id[eid])
        item.update({k: v for k, v in patch.items() if k != "notes"})
        item["revised"] = True
        item["revision_notes"] = patch.get("notes")
        item["complete"] = True
        revised.append(item)
    with out.open("w", encoding="utf-8") as f:
        for r in revised:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out
