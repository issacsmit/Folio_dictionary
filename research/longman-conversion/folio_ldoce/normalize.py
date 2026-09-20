"""Lookup-key and visible-text normalization. Hyphens and apostrophes are kept."""
from __future__ import annotations

import re
import unicodedata
from itertools import product

WS_RE = re.compile(r"[\s\u00a0\u2000-\u200b\u202f\u205f\u3000]+")
OBJECT_RE = re.compile(
    r"\b(somebody(?:['’]s)?|someone(?:['’]s)?|something|somebody|someone|sth|sb|one(?:['’]s)?)\b",
    re.I,
)
PLACEHOLDER_TOKEN_RE = re.compile(
    r"^(somebody(?:['’]s)?|someone(?:['’]s)?|something|sth|sb|one(?:['’]s)?)$",
    re.I,
)


def collapse_ws(text: str) -> str:
    return WS_RE.sub(" ", text).strip()


def empty_to_none(text: str | None) -> str | None:
    if text is None:
        return None
    text = collapse_ws(text)
    return text or None


def fold_lookup(text: str) -> str:
    """Casefold search key that keeps distinguishing periods (U. vs U)."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u2010", "-").replace("\u2011", "-")
    text = text.replace("\u00a0", " ").replace("↔", " ")
    return collapse_ws(text).casefold()


def normalize_lookup(text: str) -> str:
    """Loose key: strip surrounding punctuation so 'run.' still finds run."""
    text = fold_lookup(text)
    text = text.strip(".,;:!?·•")
    return collapse_ws(text)


def lookup_keys_for(text: str) -> list[str]:
    """Exact key first, then punctuation-stripped fallback when different."""
    keys: list[str] = []
    for item in (fold_lookup(text), normalize_lookup(text)):
        if item and item not in keys:
            keys.append(item)
    return keys


def strip_leading_dash(text: str) -> str:
    return re.sub(r"^[\s—\-–]+", "", text).strip()


def _slash_expand(text: str, cap: int = 8) -> set[str]:
    out = {text}
    if "/" not in text:
        return out
    parts = [collapse_ws(p) for p in text.split("/") if collapse_ws(p)]
    if 2 <= len(parts) <= 4 and all(" " in p for p in parts):
        out.update(parts)
        return out
    tokens = text.split(" ")
    slots: list[list[str]] = []
    n = 1
    for tok in tokens:
        if "/" in tok and "://" not in tok:
            opts = [x for x in tok.split("/") if x and x.lower() != "etc"]
            if not opts:
                opts = [tok]
            slots.append(opts)
            n *= len(opts)
            if n > cap:
                return {text}
        else:
            slots.append([tok])
    for combo in product(*slots):
        out.add(collapse_ws(" ".join(combo)))
    return out


def phrase_lookup_keys(text: str, extra: list[str] | None = None, limit: int = 16) -> list[str]:
    """Conservative retrieval variants. Does not invent unseen collocations."""
    raw = collapse_ws(text.replace("↔", " "))
    if not raw:
        return []
    variants = _slash_expand(raw)
    if extra:
        for item in extra:
            variants.update(_slash_expand(collapse_ws(item.replace("↔", " "))))
    keys: list[str] = []
    seen: set[str] = set()
    for variant in list(variants):
        for candidate in (variant, collapse_ws(OBJECT_RE.sub(" ", variant))):
            norm = normalize_lookup(candidate)
            if len(norm) < 2 or norm in seen:
                continue
            # Drop keys that are only a placeholder.
            if PLACEHOLDER_TOKEN_RE.match(norm):
                continue
            seen.add(norm)
            keys.append(norm)
            if len(keys) >= limit:
                return keys
    return keys
