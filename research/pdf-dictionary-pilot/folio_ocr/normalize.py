from __future__ import annotations

import re
import unicodedata

_SYLLABLE_DOTS = str.maketrans({"•": "", "·": "", "･": "", "․": "", ".": ""})
_HOMOGRAPH = re.compile(
    r"(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+|[1-9])$"
)
_NON_LEMMA = re.compile(r"[^a-z0-9'\-\s/]")
_MULTI_SPACE = re.compile(r"\s+")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_IPA_OK = re.compile(
    r"^[\s/\[\]a-zæɑɒəɚɛɜɝɪɨɔøʊʌʃʒθðŋɡɫɹɾwjhˈˌː.ˑ;,\-'ː:̩̝̞̟̠̃̊͜͡ʰʲᵊᵻᵿ]+$",
    re.I,
)


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def strip_homograph(display: str) -> tuple[str, int | None]:
    text = nfkc(display).strip().strip(",")
    superscripts = {
        "¹": 1,
        "²": 2,
        "³": 3,
        "⁴": 4,
        "⁵": 5,
        "⁶": 6,
        "⁷": 7,
        "⁸": 8,
        "⁹": 9,
    }
    if text and text[-1] in superscripts:
        return text[:-1].rstrip(), superscripts[text[-1]]
    m = re.search(r"([1-9])$", text)
    if m and len(text) > 1 and text[-2].isalpha():
        return text[:-1].rstrip(), int(m.group(1))
    return text, None


def dehyphen_syllables(token: str) -> str:
    if "-" not in token:
        return token
    parts = token.split("-")
    if any(len(p) >= 4 for p in parts if p):
        return token
    if all(p.isalpha() for p in parts if p):
        return "".join(parts)
    return token


def headword_key(display: str) -> str:
    text, _ = strip_homograph(display)
    text = nfkc(text).lower().strip().strip(",")
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    text = re.sub(r"[•·･․']", "", text)
    text = re.sub(r"(?<=[a-z])\.(?=[a-z])", "", text)
    text = re.sub(r"(?<=[a-z])-(?=[a-z])", "", text)
    text = _NON_LEMMA.sub(" ", text)
    return _MULTI_SPACE.sub(" ", text).strip(" -")


def phrase_key(phrase: str) -> str:
    text = nfkc(phrase).lower()
    text = text.replace("sb", " ").replace("sth", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9'\-\s]", " ", text)
    return _MULTI_SPACE.sub(" ", text).strip()


def join_hyphenated_lines(text: str) -> str:
    text = re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", text)
    text = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_ipa_regions(ipa_raw: str) -> tuple[str | None, str | None]:
    raw = nfkc(ipa_raw).strip().strip("/")
    raw = raw.replace("［", "[").replace("］", "]")
    if not raw:
        return None, None
    if "美" in raw:
        br, am = raw.split("美", 1)
        return br.strip(" ;,|"), am.strip(" ;,|") or None
    if ";" in raw and re.search(r"[A-Za-zæəɪʊʌɔɑɒʃʒθðŋˈˌː']", raw):
        left, right = raw.split(";", 1)
        if "英" in left:
            return left.replace("英", "").strip(" ;,|"), right.strip(" ;,|")
    return raw, None


def ipa_uncertain(value: str | None) -> bool:
    if not value:
        return True
    cleaned = value.replace("美", "").replace("英", "")
    if _CJK.search(cleaned):
        return True
    if re.search(r"\d", cleaned):
        return True
    compact = re.sub(r"[\s/;,\[\]'ʼˈˌː:\-]", "", cleaned)
    if len(compact) < 2:
        return True
    return _IPA_OK.fullmatch(cleaned.strip()) is None


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))
