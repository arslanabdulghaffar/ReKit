"""A bounded decoding schema; strict domain validation still decides acceptance.

Importing this module does not import the optional decoder or model runtime.
The schema controls output shape, never the truth of a visual assertion.
"""

import hashlib
import json
import logging
from typing import Any


SCHEMA_VERSION = "rekit-inspection-schema-v2"


def inspection_schema(image_count: int, *, allow_candidates: bool = True) -> dict:
    """Return a fresh schema for exactly the images admitted to this request."""
    if type(image_count) is not int or image_count not in (1, 2):
        raise ValueError("image_count must be one or two")
    if type(allow_candidates) is not bool:
        raise ValueError("Candidate permission must be an explicit boolean")

    def text(limit: int) -> dict:
        # LMFE 0.11.3 rejects pattern combined with length constraints. Domain
        # validators separately reject whitespace-only text and invalid IDs.
        return {"type": "string", "minLength": 1, "maxLength": limit}

    def indices() -> dict:
        # Numeric bounds and uniqueItems are not enforced by this decoder.
        # Enumerate valid indices; the domain parser still checks uniqueness.
        return {"type": "array", "items": {"type": "integer", "enum": list(range(1, image_count + 1))},
                "minItems": 1, "maxItems": image_count}

    def record(properties: dict) -> dict:
        return {"type": "object", "properties": properties,
                "required": list(properties), "additionalProperties": False}

    def array(items: dict, maximum: int, minimum: int = 0) -> dict:
        return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}

    observation = record({
        "image_indices": indices(),
        "kind": {"type": "string", "enum": ["appearance", "marking", "visible_damage", "missing_information"]},
        "text": text(160),
    })
    candidates = []
    for revision_known in (False, True):
        candidates.append(record({
            "image_indices": indices(),
            "component_type_id": text(128),
            "revision": text(128) if revision_known else {"type": "null"},
            "revision_marking": text(160) if revision_known else {"type": "null"},
            "reason": text(160),
        }))
    view = record({"image_indices": indices(), "view": text(100), "reason": text(160)})
    return record({
        "observations": array(observation, 2),
        "candidates": array({"anyOf": candidates}, 1 if allow_candidates else 0),
        "uncertainties": array(text(160), 2, 1),
        "additional_views": array(view, 1),
    })


def schema_digest(schema: dict) -> str:
    """Hash the exact canonical decoder schema, including input-index bounds."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _RedactDecoderLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # The pinned library uses logging.exception/debug on the root logger,
        # embedding decoded prefixes and exception text. Redact only that file;
        # do not disable application logging or expose raw image-derived text.
        source = record.pathname.replace("\\", "/")
        if source.endswith("/lmformatenforcer/tokenenforcer.py"):
            record.msg = "Structured decoder reported an internal parser error; output requires strict validation"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


_LOG_FILTER = _RedactDecoderLogs()


def _protect_decoder_logs() -> None:
    logging.getLogger().addFilter(_LOG_FILTER)


def build_tokenizer_data(tokenizer: Any) -> Any:
    """Prepare reusable vocabulary data; callers cache it with the tokenizer."""
    _protect_decoder_logs()
    from lmformatenforcer.integrations.transformers import build_token_enforcer_tokenizer_data

    return build_token_enforcer_tokenizer_data(tokenizer)


def build_character_parser(schema: dict) -> Any:
    """Enforce the schema plus the pinned decoder's missing empty-array bound.

    LMFE 0.11.3 checks maxItems only after its first item. Keep a narrow,
    immutable character guard for the top-level candidates array when no
    catalog was supplied. Never patch the installed package or rewrite output.
    """
    from lmformatenforcer import JsonSchemaParser

    parser = JsonSchemaParser(schema)
    if schema.get("properties", {}).get("candidates", {}).get("maxItems") != 0:
        return parser
    from lmformatenforcer.characterlevelparser import CharacterLevelParser

    class EmptyCandidatesGuard(CharacterLevelParser):
        def __init__(self, inner, depth=0, quoted=False, escaped=False,
                     key_text="", key="", phase=""):
            self.inner = inner
            self.depth, self.quoted, self.escaped = depth, quoted, escaped
            self.key_text, self.key, self.phase = key_text, key, phase

        @property
        def config(self):
            return self.inner.config

        @config.setter
        def config(self, value):
            self.inner.config = value

        def get_allowed_characters(self):
            allowed = self.inner.get_allowed_characters()
            if self.phase:
                permitted = ("[" if self.phase == "open" else "]") + " \t\r\n"
                return "".join(c for c in allowed if c in permitted)
            return allowed

        def can_end(self):
            return not self.phase and self.inner.can_end()

        def shortcut_key(self):
            return None if self.phase else self.inner.shortcut_key()

        def add_character(self, character):
            if character not in self.get_allowed_characters():
                raise ValueError("Character violates the admitted output schema")
            depth, quoted, escaped = self.depth, self.quoted, self.escaped
            key_text, key, phase = self.key_text, self.key, self.phase
            if quoted:
                if depth == 1:
                    key_text += character
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
                    if depth == 1:
                        key = json.loads(key_text)
            elif character == '"':
                quoted, key_text = True, '"'
            elif character == ":" and depth == 1 and key == "candidates":
                phase = "open"
            elif character in "[{":
                depth += 1
                if phase == "open":
                    phase = "close"
            elif character in "]}":
                depth -= 1
                if phase == "close":
                    phase = ""
            return EmptyCandidatesGuard(self.inner.add_character(character), depth,
                                        quoted, escaped, key_text, key, phase)

    return EmptyCandidatesGuard(parser)


def build_prefix(tokenizer: Any, schema: dict) -> Any:
    """Build fresh request state from a tokenizer or its reusable LMFE data."""
    _protect_decoder_logs()
    from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn

    return build_transformers_prefix_allowed_tokens_fn(tokenizer, build_character_parser(schema))
