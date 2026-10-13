"""Parse one bounded model JSON object without repairing or inventing evidence."""

import json
import re

from rekit.inference.models import InspectionOutput


MAX_OUTPUT_CHARACTERS = 32_000
_JSON_FENCE = re.compile(r"\A```json[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```\Z")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Model JSON contains a duplicate object key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Model JSON cannot contain non-finite numeric constants")


def parse_output(raw: str, image_count: int, *, allow_candidates: bool = True) -> InspectionOutput:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_OUTPUT_CHARACTERS:
        raise ValueError("Model output must contain one JSON object of at most 32000 characters")
    if type(image_count) is not int or image_count not in (1, 2):
        raise ValueError("An inference output requires one or two actual input images")
    if type(allow_candidates) is not bool:
        raise ValueError("Candidate permission must be an explicit boolean")
    text = raw.strip()
    fenced = _JSON_FENCE.fullmatch(text)
    if fenced:
        text = fenced.group("body")
    try:
        payload = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Model output is not a single valid JSON object") from error
    if not isinstance(payload, dict):
        raise ValueError("Model output must be a JSON object")
    output = InspectionOutput.model_validate(payload)
    output.validate_image_count(image_count)
    if not allow_candidates and output.candidates:
        raise ValueError("Identity candidates require a supplied approved catalog")
    return output
