from __future__ import annotations

import json
import re
from pathlib import Path

from .config import OCR_DIR, OUTPUT_DIR, POS_TOKENS, SAMPLE_PAGES, ensure_output_dirs
from .layout import is_feature_title, line_in_box
from .normalize import (
    has_cjk,
    headword_key,
    ipa_uncertain,
    join_hyphenated_lines,
    nfkc,
    phrase_key,
    split_ipa_regions,
    strip_homograph,
)
from .ocr import ocr_json_path

WINDOWS = [
    list(range(98, 106)),
    list(range(498, 506)),
    list(range(998, 1006)),
    list(range(1998, 2006)),
]

_SENSE_SPLIT = re.compile(
    r"(?:(?<=\s)|^)([1-9]\d?)\s+(?=[A-Za-z\(\[【\u4e00-\u9fff“\"'])"
)
_LABEL = re.compile(
    r"【[^】]{1,20}】|〔[^〕]{1,20}〕|\[[CTUI](?:,[CTUI])?(?:[^\]]{0,40})?\]|"
    r"\b(?:BrE|AmE|informal|formal|spoken|written|old-fashioned|literary|"
    r"humorous|legal|medical|technical|trademark|taboo|biblical)\b"
)
_FREQ_JUNK = re.compile(
    r"[●○◆◇■□]+|\b[SWsw][123]\b|\boO\b|\bOO\b|\b00\b|\b○O\b"
)
_POS_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in POS_TOKENS) + r"|phr v|phrasal verb)\b",
    re.I,
)
_HEAD_START = re.compile(r"^,?[A-Za-z]")
_ARROW = re.compile(r"^(→|见|->|see picture|see also|SYN|ANT)\b", re.I)
_ENGLISHISH_IPA = {
    "everything",
    "everyone",
    "everybody",
    "something",
    "someone",
    "somewhere",
    "just",
    "about",
    "take",
    "get",
    "with",
    "from",
    "that",
    "this",
    "next",
    "almost",
    "nearly",
    "pretty",
    "much",
    "understand",
    "agree",
    "evening",
    "january",
    "speak",
    "reply",
    "fiscal",
    "year",
    "point",
    "cold",
}
_COLO_PREFIX = re.compile(
    r"^(?:a|an|the|or|and|but|if|when|used|have|has|had|get|got|take|make|give|see|put|in|on|at|to|from|not)\s",
    re.I,
)
_POS_HEAD = re.compile(
    r"^,?([A-Za-z][A-Za-z•·.\-' ]{0,40}?)([¹²³⁴⁵⁶⁷⁸⁹1-9]{1,2})?\s+"
    r"(n|v|adj|adv|prep|pron|det|conj|phr\s*v)\b",
    re.I,
)


def load_page(page: int) -> dict | None:
    path = ocr_json_path(page)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _col_left(layout: dict, column: int) -> float:
    cols = layout.get("columns") or []
    if column < len(cols):
        return float(cols[column][0])
    return 0.0


def merge_baseline_lines(lines: list[dict]) -> list[dict]:
    """Join OCR boxes that sit on the same printed line."""
    ordered = sorted(
        lines, key=lambda r: (r["page"], r.get("column", 0), r["y0"], r["x0"])
    )
    out: list[dict] = []
    for ln in ordered:
        cur = dict(ln)
        if out:
            prev = out[-1]
            same = (
                prev["page"] == cur["page"]
                and prev.get("column", 0) == cur.get("column", 0)
            )
            if same:
                overlap = min(prev["y1"], cur["y1"]) - max(prev["y0"], cur["y0"])
                h = min(prev["y1"] - prev["y0"], cur["y1"] - cur["y0"])
                if h > 0 and overlap / h >= 0.45:
                    left, right = (cur, prev) if cur["x0"] < prev["x0"] else (prev, cur)
                    gap = right["x0"] - left["x1"]
                    sep = "" if gap < 10 else " "
                    if re.search(r"[¹²³⁴⁵⁶⁷⁸⁹0-9]$", left.get("text") or "") and re.match(
                        r"^[A-Za-z]", right.get("text") or ""
                    ):
                        sep = " "
                    prev["text"] = (left.get("text") or "").rstrip() + sep + (
                        right.get("text") or ""
                    ).lstrip()
                    prev["x0"] = min(prev["x0"], cur["x0"])
                    prev["x1"] = max(prev["x1"], cur["x1"])
                    prev["y0"] = min(prev["y0"], cur["y0"])
                    prev["y1"] = max(prev["y1"], cur["y1"])
                    prev["score"] = min(prev.get("score") or 1, cur.get("score") or 1)
                    continue
        out.append(cur)
    return out


def ipa_is_phonetic(ipa: str) -> bool:
    s = nfkc(ipa).strip()
    if not s or len(s) > 90:
        return False
    if "(=" in s or re.search(r"\betc\b", s, re.I):
        return False
    words = [t.lower() for t in re.findall(r"[A-Za-z]{3,}", s)]
    if any(t in _ENGLISHISH_IPA for t in words):
        return False
    if re.search(r"[æɑɒəɚɛɜɝɪɨɔøʊʌʃʒθðŋɡˈˌː:美英]", s):
        return True
    return len(words) <= 2 and len(s) <= 40


def is_sense_banner(text: str) -> bool:
    t = _FREQ_JUNK.sub(" ", text or "")
    t = re.sub(r"[\d\[\]/●○·.•,;:]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    letters = re.sub(r"[^A-Za-z]", "", t)
    if len(letters) < 3 or len(t.split()) > 8:
        return False
    return letters.isupper()


def _looks_like_headword(text: str, next_text: str | None = None) -> bool:
    t = nfkc(text or "").strip()
    if not t or not _HEAD_START.match(t):
        return False
    if is_feature_title(t) or is_sense_banner(t):
        return False
    if re.match(r"^\d+\s+\S", t) and not re.search(r"/[^/]{1,40}/", t[:50]):
        return False
    if "(=" in t[:55]:
        return False
    m_ipa = re.search(r"/([^/\n]{1,80})/", t[:140])
    if m_ipa and ipa_is_phonetic(m_ipa.group(1)):
        left = t[: m_ipa.start()].strip()
        if "/" in left or left.count(" ") > 7:
            return False
        if _COLO_PREFIX.match(left):
            return False
        if re.match(r"^,?[A-Za-z]", left):
            return True
    t_pos = _FREQ_JUNK.sub(" ", t)
    t_pos = re.sub(r"\s+", " ", t_pos).strip()
    m_pos = _POS_HEAD.match(t_pos)
    if m_pos:
        lemma = (m_pos.group(1) or "").strip()
        if len(re.sub(r"[^A-Za-z]", "", lemma)) < 2:
            return False
        if re.fullmatch(r"[SWsw][123]", lemma):
            return False
        if t.startswith(",") or m_pos.group(2) or re.search(r"[·•'\-]", lemma):
            return True
        if m_pos.group(3).lower().startswith("phr"):
            return True
    t_short = _FREQ_JUNK.sub(" ", t)
    t_short = re.sub(r"\s+", " ", t_short).strip()
    if re.fullmatch(r",?[A-Za-z][A-Za-z•·.\-' ]{1,24}[¹²³⁴⁵⁶⁷⁸⁹1-9]?", t_short):
        nxt = nfkc(next_text or "")
        m_n = re.search(r"/([^/]{1,80})/", nxt[:90])
        if m_n and ipa_is_phonetic(m_n.group(1)):
            return True
        if re.match(
            r"^\s*(?:[SWsw][123]\s*)*(n|v|adj|adv|phr\s*v)\b", nxt, re.I
        ):
            return True
        if re.match(r"^\s*1\s+", nxt):
            return True
    return False


def classify_line(
    text: str,
    next_text: str | None,
    in_feature: bool,
    feature_kind: str | None,
) -> str:
    t = (text or "").strip()
    if not t:
        return "empty"
    if is_feature_title(t):
        return "feature_title"
    if _ARROW.match(t) and "/" not in t[:40]:
        return "xref"
    if _looks_like_headword(t, next_text):
        return "headword"
    if in_feature and feature_kind == "collocations":
        return "collocation_line"
    if in_feature and feature_kind in {"thesaurus", "grammar", "usage"}:
        return "feature_body"
    if re.match(r"^\d+\s+\S", t):
        return "sense"
    return "body"


def _feature_kind(text: str) -> str:
    u = text.upper()
    if "COLLOCATION" in u or "词语搭配" in text:
        return "collocations"
    if "THESAURUS" in u or "辨析" in text:
        return "thesaurus"
    if "GRAMMAR" in u or "语法" in text:
        return "grammar"
    if "USAGE" in u or "REGISTER" in u:
        return "usage"
    return "feature"


def _clean_headword_display(raw: str) -> str:
    text = nfkc(raw)
    text = _FREQ_JUNK.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;:")
    return text


def _extract_head_ipa_rest(first: str, rest_lines: list[str]) -> tuple[str, str | None, str]:
    blob = join_hyphenated_lines(first + " " + " ".join(rest_lines))
    first_n = nfkc(first)
    m = re.search(r"^(,?.{1,48}?)(?:\s*)/([^/]{1,90})/(.*)$", first_n)
    if m:
        hw = _clean_headword_display(m.group(1))
        ipa = m.group(2).strip()
        rest = join_hyphenated_lines(m.group(3) + " " + " ".join(rest_lines))
        return hw, ipa, rest
    m = re.search(r"^(,?.{1,48}?)(?:\s*)/([^/]{1,90})/(.*)$", blob)
    if m:
        return _clean_headword_display(m.group(1)), m.group(2).strip(), m.group(3).strip()
    # no IPA
    mpos = _POS_RE.search(first_n)
    if mpos:
        hw = _clean_headword_display(first_n[: mpos.start()])
        rest = join_hyphenated_lines(first_n[mpos.start() :] + " " + " ".join(rest_lines))
        return hw, None, rest
    hw = _clean_headword_display(re.split(r"\s{2,}|\s(?=\d+\s)", first_n, maxsplit=1)[0])
    rest = join_hyphenated_lines(" ".join(rest_lines))
    return hw, None, rest


def _extract_pos(text: str) -> str | None:
    m = _POS_RE.search(text[:120] if text else "")
    if not m:
        return None
    pos = m.group(1).lower()
    if pos == "phrasal verb":
        return "phr v"
    return pos


def _strip_leading_pos_infl(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^\((?:plural|singular|allied|[^\)]{0,40})\)\s*", "", t, flags=re.I)
    t = re.sub(
        r"^(?:linking verb|modal verb|phr v|phrasal verb|predeterminer|determiner|"
        r"exclamation|abbreviation|prefix|suffix|number|pron|prep|conj|det|adj|adv|n|v)\s*",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(r"^\((?:plural|singular)[^)]{0,40}\)\s*", "", t, flags=re.I)
    t = re.sub(r"^\[(?:C|U|T|I)[^\]]{0,60}\]\s*", "", t)
    return t.strip(" ;,")


def _split_senses(body: str) -> list[tuple[str, str]]:
    body = body.strip()
    if not body:
        return []
    matches = list(_SENSE_SPLIT.finditer(body))
    if not matches:
        return [("1", body)]
    # if the first sense number isn't at the start, keep preamble with sense 1
    out = []
    if matches[0].start() > 0:
        pre = body[: matches[0].start()].strip()
        if pre and has_cjk(pre) or len(pre) > 12:
            out.append(("1", pre))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[m.end() : end].strip()
        out.append((m.group(1), chunk))
    return out or [("1", body)]


def _labels_and_core(chunk: str) -> tuple[list[str], str]:
    labels = [m.group(0) for m in _LABEL.finditer(chunk)]
    core = chunk
    for lab in labels:
        core = core.replace(lab, " ", 1)
    core = re.sub(r"\s+", " ", core).strip(" ;,")
    return labels, core


def _first_zh_gloss(text: str) -> str | None:
    m = re.search(r"[\u4e00-\u9fff]", text or "")
    if not m:
        return None
    s = text[m.start() :]
    out: list[str] = []
    i = 0
    while i < len(s) and len(out) < 50:
        ch = s[i]
        if "\u4e00" <= ch <= "\u9fff" or ch in "、，。；！？“”‘’【】〔〕（）…—·《》-—/ ":
            out.append(ch)
            i += 1
            continue
        if ch in ":：|":
            break
        m2 = re.match(r"[A-Za-z]{2,16}", s[i:])
        if m2:
            break
        i += 1
    zh = "".join(out).strip(" ，、；:：|")
    return zh or None


def _split_en_zh_examples(core: str) -> tuple[str | None, str | None, list[dict]]:
    """Return English gloss, Chinese definition, inline collocations. Drop examples."""
    m_cjk = re.search(r"[\u4e00-\u9fff]", core)
    if not m_cjk:
        en = _strip_leading_pos_infl(core)
        en = re.sub(r"\s+", " ", en).strip(" ;,")
        return (en or None), None, []
    en = core[: m_cjk.start()].strip(" :：,;|")
    en = _strip_leading_pos_infl(en)
    rest = core[m_cjk.start() :].strip()
    parts = [p.strip() for p in re.split(r"\s*\|\s*", rest) if p.strip()]
    zh = _first_zh_gloss(parts[0]) if parts else _first_zh_gloss(rest)
    collocations = []
    for extra in parts[1:]:
        col = _collocation_from_segment(extra)
        if col:
            collocations.append(col)
    return (en or None), (zh or None), collocations


def _collocation_from_segment(seg: str) -> dict | None:
    seg = seg.strip()
    if not seg or not has_cjk(seg):
        return None
    m = re.search(r"[\u4e00-\u9fff]", seg)
    en = seg[: m.start()].strip(" :：,;=")
    zh_rest = seg[m.start() :]
    cut = re.search(r"[：:](?=\s*[A-Za-z])|(?<=[。；！？])(?=\s*[A-Z])", zh_rest)
    zh = zh_rest[: cut.start()].strip() if cut else zh_rest
    zh = re.sub(r"[A-Za-z][A-Za-z'].{6,}$", "", zh).strip(" :：,;|")
    en = re.sub(r"\s+", " ", en)
    en = re.sub(r"^\(=.*?\)\s*", "", en)
    if not en or len(en) > 80:
        return None
    if en.endswith(".") and len(en.split()) > 9:
        return None
    key = phrase_key(en)
    if not key or len(key) < 2:
        return None
    return {
        "phrase_display": en.strip(" |"),
        "phrase_key": key,
        "explanation_zh": zh or None,
        "source": "sense_inline",
        "labels": [],
    }


def _parse_collocation_line(text: str) -> dict | None:
    t = join_hyphenated_lines(text)
    t = re.sub(r"^(VERBS|ADJECTIVES|NOUNS|ADVERBS|PREPOSITIONS).{0,20}", "", t, flags=re.I)
    t = t.strip(" •·|-")
    if not t or is_feature_title(t):
        return None
    return _collocation_from_segment(t)


def _union_bbox(lines: list[dict]) -> dict | None:
    if not lines:
        return None
    return {
        "x0": min(l["x0"] for l in lines),
        "y0": min(l["y0"] for l in lines),
        "x1": max(l["x1"] for l in lines),
        "y1": max(l["y1"] for l in lines),
        "page": lines[0].get("page"),
        "pages": sorted({l["page"] for l in lines}),
    }


def parse_window(pages: list[int]) -> list[dict]:
    stream = []
    page_docs = {}
    for page in pages:
        doc = load_page(page)
        if not doc or doc.get("status") != "ok":
            continue
        page_docs[page] = doc
        layout = doc.get("layout") or {}
        boxes = layout.get("feature_boxes") or []
        for ln in doc.get("lines") or []:
            item = dict(ln)
            item["page"] = page
            col = int(item.get("column") or 0)
            item["col_left"] = _col_left(layout, col)
            item["feature_box"] = None
            for b in boxes:
                if line_in_box(item, b):
                    item["feature_box"] = b
                    break
            stream.append(item)
    stream = merge_baseline_lines(stream)

    entries_raw: list[list[dict]] = []
    current: list[dict] = []
    feature_kind = None
    in_feature = False
    for i, item in enumerate(stream):
        text = item.get("text") or ""
        nxt = stream[i + 1].get("text") if i + 1 < len(stream) else ""
        kind = classify_line(
            text,
            nxt,
            in_feature=in_feature,
            feature_kind=feature_kind,
        )
        item["line_kind"] = kind
        if kind == "feature_title":
            in_feature = True
            feature_kind = _feature_kind(text)
            if current:
                current.append(item)
            continue
        if kind == "headword":
            in_feature = False
            feature_kind = None
            if current:
                entries_raw.append(current)
            current = [item]
            continue
        if current:
            current.append(item)
        else:
            current = [item]
            item["line_kind"] = "orphan" if kind != "headword" else kind
        if in_feature:
            box = item.get("feature_box")
            if not box or item["y0"] > box["y1"] + 12:
                in_feature = False
                feature_kind = None
    if current:
        entries_raw.append(current)

    parsed = []
    for idx, elines in enumerate(entries_raw):
        parsed.append(_build_entry(elines, idx))
    return parsed


def _build_entry(elines: list[dict], idx: int) -> dict:
    pages = sorted({e["page"] for e in elines})
    sample_pages = [p for p in pages if p in SAMPLE_PAGES]
    head_lines = [e for e in elines if e.get("line_kind") == "headword"]
    started_ok = bool(head_lines) and elines[0].get("line_kind") == "headword"
    first = elines[0]
    head_src = head_lines[0] if head_lines else first
    rest_after_head = []
    seen_head = False
    colo_lines = []
    body_lines = []
    for e in elines:
        if e.get("line_kind") == "headword" and not seen_head:
            seen_head = True
            continue
        if e.get("line_kind") == "collocation_line":
            colo_lines.append(e)
        if e.get("line_kind") in {"feature_title", "feature_body"}:
            continue
        rest_after_head.append(e.get("text") or "")
        body_lines.append(e)

    hw, ipa_raw, rest = _extract_head_ipa_rest(head_src.get("text") or "", rest_after_head)
    display, homograph = strip_homograph(hw)
    key = headword_key(display)
    pos = _extract_pos((head_src.get("text") or "") + " " + rest[:80])
    if pos:
        pos = {"n": "n", "v": "v", "adj": "adj", "adv": "adv"}.get(pos.lower(), pos.lower())
    ipa_br, ipa_am = split_ipa_regions(ipa_raw or "") if ipa_raw else (None, None)
    rest_body = _strip_leading_pos_infl(rest)
    senses = []
    inline_cols = []
    for no, chunk in _split_senses(rest_body):
        labels, core = _labels_and_core(chunk)
        en, zh, cols = _split_en_zh_examples(core)
        senses.append(
            {
                "sense_no": no,
                "labels": labels,
                "definition_en": en,
                "definition_zh": zh,
            }
        )
        for c in cols:
            c["sense_no"] = no
            inline_cols.append(c)
    for cl in colo_lines:
        col = _parse_collocation_line(cl.get("text") or "")
        if col:
            col["source"] = "collocations_box"
            inline_cols.append(col)

    # phrasal-style headword as self collocation
    if pos == "phr v" or re.search(r"\bsb\b|\bsth\b", display, re.I):
        zh0 = next((s["definition_zh"] for s in senses if s.get("definition_zh")), None)
        inline_cols.insert(
            0,
            {
                "phrase_display": display,
                "phrase_key": phrase_key(display),
                "explanation_zh": zh0,
                "source": "phrasal",
                "labels": [],
            },
        )

    complete = True
    reasons = []
    if not started_ok or not key:
        complete = False
        reasons.append("truncated_start_or_missing_headword")
    if not any(s.get("definition_zh") for s in senses):
        complete = False
        reasons.append("missing_chinese")
    if not sample_pages:
        role = "context_only"
    else:
        role = "sample"

    bbox = _union_bbox(elines)
    return {
        "id": f"p{pages[0]:04d}-c{head_src.get('column', 0)}-y{int(head_src.get('y0', 0)):04d}-{idx:03d}",
        "headword_display": display or (head_src.get("text") or "")[:40],
        "headword_key": key,
        "homograph": homograph,
        "pos": pos,
        "ipa_raw": ipa_raw,
        "ipa_br": ipa_br,
        "ipa_am": ipa_am,
        "ipa_uncertain": bool(ipa_uncertain(ipa_raw) if ipa_raw else True),
        "complete": complete and role == "sample",
        "incomplete_reason": None if (complete and role == "sample") else ",".join(reasons) or role,
        "role": role,
        "page_start": pages[0],
        "page_end": pages[-1],
        "pages": pages,
        "sample_pages": sample_pages,
        "column_start": head_src.get("column"),
        "bbox": bbox,
        "senses": senses,
        "collocations": inline_cols,
        "raw_ocr": join_hyphenated_lines(" ".join(e.get("text") or "" for e in elines)),
        "line_count": len(elines),
        "mean_line_score": round(
            sum(e.get("score") or 0 for e in elines) / max(len(elines), 1), 4
        ),
    }


def parse_all() -> list[dict]:
    ensure_output_dirs()
    entries = []
    errors = []
    for window in WINDOWS:
        missing = [p for p in window if not ocr_json_path(p).exists()]
        if missing:
            errors.append({"window": window, "missing_pages": missing})
        entries.extend(parse_window(window))
    auto_path = OUTPUT_DIR / "entries.auto.jsonl"
    with auto_path.open("w", encoding="utf-8") as f:
        for e in entries:
            if e.get("role") == "context_only":
                continue
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    debug_path = OUTPUT_DIR / "entries.debug.jsonl"
    with debug_path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    summary = {
        "n_total_including_context": len(entries),
        "n_sample": sum(1 for e in entries if e.get("role") == "sample"),
        "n_complete": sum(1 for e in entries if e.get("complete")),
        "n_incomplete_sample": sum(
            1 for e in entries if e.get("role") == "sample" and not e.get("complete")
        ),
        "errors": errors,
        "auto_jsonl": str(auto_path),
    }
    (OUTPUT_DIR / "parse_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return entries
