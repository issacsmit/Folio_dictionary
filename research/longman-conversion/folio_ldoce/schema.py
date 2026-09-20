"""Folio dictionary pack v1 schemas."""
from __future__ import annotations

MANIFEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "format",
        "format_version",
        "pack_id",
        "parser_version",
        "source",
        "languages",
        "files",
        "counts",
        "checksums",
    ],
    "properties": {
        "format": {"const": "folio-dict-pack"},
        "format_version": {"type": "string"},
        "pack_id": {"type": "string"},
        "parser_version": {"type": "string"},
        "generated_at": {"type": "string"},
        "source": {
            "type": "object",
            "required": ["name", "mdx_path", "mdx_sha256", "mdx_bytes"],
            "properties": {
                "name": {"type": "string"},
                "mdx_path": {"type": "string"},
                "mdx_sha256": {"type": "string"},
                "mdx_bytes": {"type": "integer"},
                "header": {"type": "object"},
                "rights_note": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "languages": {"type": "object"},
        "files": {"type": "array", "items": {"type": "string"}},
        "counts": {"type": "object"},
        "checksums": {"type": "object"},
        "content_policy": {"type": "object"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
}

LABEL_SCHEMA = {
    "type": "object",
    "required": ["type", "value"],
    "properties": {
        "type": {"enum": ["register", "geo", "domain", "other"]},
        "value": {"type": "string"},
        "scope": {"enum": ["entry", "pos", "sense", "phrase"]},
    },
    "additionalProperties": False,
}

DEFINITION_SCHEMA = {
    "type": "object",
    "required": ["en", "zh"],
    "properties": {
        "en": {"type": ["string", "null"]},
        "zh": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}

XREF_SCHEMA = {
    "type": "object",
    "required": ["text"],
    "properties": {
        "text": {"type": "string"},
        "href": {"type": ["string", "null"]},
        "homograph": {"type": ["integer", "null"]},
        "sense": {"type": ["string", "null"]},
        "relation": {"type": "string"},
    },
    "additionalProperties": False,
}

PHRASE_SCHEMA = {
    "type": "object",
    "required": ["id", "type", "text", "definition"],
    "properties": {
        "id": {"type": "string"},
        "type": {
            "enum": [
                "idiom",
                "phrasal_verb",
                "collocation",
                "pattern",
                "lexical_unit",
                "spoken",
            ]
        },
        "text": {"type": "string"},
        "definition": DEFINITION_SCHEMA,
        "labels": {"type": "array", "items": LABEL_SCHEMA},
        "sense_id": {"type": ["string", "null"]},
        "patterns": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

SENSE_SCHEMA = {
    "type": "object",
    "required": ["id", "definition"],
    "properties": {
        "id": {"type": "string"},
        "number": {"type": ["string", "null"]},
        "signpost": {
            "type": ["object", "null"],
            "properties": {
                "en": {"type": ["string", "null"]},
                "zh": {"type": ["string", "null"]},
            },
        },
        "grammar": {"type": "array", "items": {"type": "string"}},
        "labels": {"type": "array", "items": LABEL_SCHEMA},
        "patterns": {"type": "array", "items": {"type": "string"}},
        "lexunits": {"type": "array", "items": {"type": "string"}},
        "definition": DEFINITION_SCHEMA,
        "cross_refs": {"type": "array", "items": XREF_SCHEMA},
        "phrases": {"type": "array", "items": PHRASE_SCHEMA},
        "senses": {"type": "array"},
    },
    "additionalProperties": False,
}
SENSE_SCHEMA["properties"]["senses"]["items"] = SENSE_SCHEMA

ENTRY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "kind", "headword", "source", "pos_groups"],
    "properties": {
        "id": {"type": "string"},
        "kind": {"enum": ["word", "derived", "phrasal_verb", "see_also"]},
        "headword": {"type": "string"},
        "display": {"type": "string"},
        "homograph": {"type": ["integer", "null"]},
        "source": {
            "type": "object",
            "required": ["mdx_keys"],
            "properties": {
                "mdx_keys": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "anchor": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "pronunciations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["ipa", "accent"],
                "properties": {
                    "ipa": {"type": "string"},
                    "accent": {"enum": ["br", "us", "unspecified"]},
                    "raw": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "frequency": {
            "type": ["object", "null"],
            "properties": {
                "stars": {"type": ["string", "null"]},
                "spoken": {"type": ["string", "null"]},
                "written": {"type": ["string", "null"]},
            },
        },
        "inflections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "form"],
                "properties": {
                    "type": {"type": "string"},
                    "form": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "pos_groups": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pos", "senses"],
                "properties": {
                    "pos": {"type": "array", "items": {"type": "string"}},
                    "grammar": {"type": "array", "items": {"type": "string"}},
                    "labels": {"type": "array", "items": LABEL_SCHEMA},
                    "senses": {"type": "array", "items": SENSE_SCHEMA},
                },
                "additionalProperties": False,
            },
        },
        "phrases": {"type": "array", "items": PHRASE_SCHEMA},
        "cross_refs": {"type": "array", "items": XREF_SCHEMA},
        "parent": {
            "type": ["object", "null"],
            "properties": {
                "id": {"type": ["string", "null"]},
                "headword": {"type": "string"},
                "relation": {"type": "string"},
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

LOOKUP_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["norm", "matches"],
    "properties": {
        "norm": {"type": "string", "minLength": 1},
        "matches": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["entry_id", "match"],
                "properties": {
                    "entry_id": {"type": "string"},
                    "sense_id": {"type": ["string", "null"]},
                    "match": {"type": "string"},
                    "headword": {"type": "string"},
                    "key_raw": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

LEDGER_SCHEMA = {
    "type": "object",
    "required": ["key", "status"],
    "properties": {
        "key": {"type": "string"},
        "status": {"type": "string"},
        "entry_ids": {"type": "array", "items": {"type": "string"}},
        "link_target": {"type": ["string", "null"]},
        "reason": {"type": ["string", "null"]},
        "issues": {"type": "integer"},
    },
    "additionalProperties": True,
}
