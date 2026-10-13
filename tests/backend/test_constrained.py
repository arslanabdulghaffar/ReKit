"""Decoder shape tests; none establish visual truth or require model weights."""

import copy
import json
import logging
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest

from rekit.inference.constrained import (
    SCHEMA_VERSION, _protect_decoder_logs, build_prefix, build_tokenizer_data,
    inspection_schema, schema_digest,
)
from rekit.inference.parsing import parse_output


def output():
    return {"observations": [{"image_indices": [1], "kind": "appearance", "text": "Red shape"}],
            "candidates": [{"image_indices": [1], "component_type_id": "body", "revision": None,
                            "revision_marking": None, "reason": "Visible housing"}],
            "uncertainties": ["Identity requires human review"], "additional_views": []}


@pytest.mark.parametrize("count", [True, False, 0, 3, "1", 1.0, None])
def test_schema_rejects_invalid_image_count(count):
    with pytest.raises(ValueError):
        inspection_schema(count)


def test_schema_is_fresh_bounded_and_digest_covers_source_count():
    schema = inspection_schema(2)
    assert schema["required"] == ["observations", "candidates", "uncertainties", "additional_views"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["observations"]["maxItems"] == 2
    assert schema["properties"]["candidates"]["maxItems"] == 1
    assert schema["properties"]["uncertainties"]["minItems"] == 1
    assert schema["properties"]["additional_views"]["maxItems"] == 1
    branches = schema["properties"]["candidates"]["items"]["anyOf"]
    assert all(branch["additionalProperties"] is False for branch in branches)
    assert branches[0]["properties"]["revision"] == {"type": "null"}
    assert branches[0]["properties"]["revision_marking"] == {"type": "null"}
    assert branches[1]["properties"]["revision"]["minLength"] == 1
    assert branches[1]["properties"]["revision_marking"]["minLength"] == 1
    assert "pattern" not in json.dumps(schema)
    assert schema_digest(schema) != schema_digest(inspection_schema(1))
    assert schema_digest(schema) == schema_digest(dict(reversed(list(schema.items()))))
    schema["properties"]["observations"]["maxItems"] = 99
    assert inspection_schema(2)["properties"]["observations"]["maxItems"] == 2
    assert SCHEMA_VERSION == "rekit-inspection-schema-v1"


def test_optional_runtime_is_not_imported_by_schema_helpers():
    script = """
import importlib.abc
import sys
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'transformers', 'lmformatenforcer', 'interegular'}:
            raise AssertionError('unexpected optional import: ' + fullname)
sys.meta_path.insert(0, BlockOptional())
from rekit.inference.constrained import inspection_schema, schema_digest
assert len(schema_digest(inspection_schema(2))) == 64
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).parents[2],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr


def test_prefix_builders_use_fresh_parser_and_reusable_tokenizer_data(monkeypatch):
    package = ModuleType("lmformatenforcer")
    integration = ModuleType("lmformatenforcer.integrations.transformers")
    parsers = []
    calls = []

    class Parser:
        def __init__(self, schema):
            self.schema = schema
            parsers.append(self)

    package.JsonSchemaParser = Parser
    integration.build_token_enforcer_tokenizer_data = lambda tokenizer: ("prepared", tokenizer)
    integration.build_transformers_prefix_allowed_tokens_fn = lambda data, parser: calls.append((data, parser)) or object()
    monkeypatch.setitem(sys.modules, "lmformatenforcer", package)
    monkeypatch.setitem(sys.modules, "lmformatenforcer.integrations.transformers", integration)
    data = build_tokenizer_data("test tokenizer")
    first = build_prefix(data, inspection_schema(1))
    second = build_prefix(data, inspection_schema(2))
    assert first is not second
    assert parsers[0] is not parsers[1]
    assert calls[0][0] is calls[1][0] is data


def test_only_decoder_prefix_logs_are_redacted_before_handlers(caplog):
    _protect_decoder_logs()
    private = "PRIVATE MODEL PREFIX AND PROMPT"
    record = logging.LogRecord("root", logging.ERROR,
                               "C:/runtime/lmformatenforcer/tokenenforcer.py", 136,
                               private + " %s", (private,), (RuntimeError, RuntimeError(private), None))
    record.exc_text = private
    record.stack_info = private
    logging.getLogger().handle(record)
    assert private not in caplog.text
    assert "Structured decoder" in caplog.text
    assert record.exc_info is None and record.exc_text is None and record.stack_info is None
    logging.getLogger().error("ordinary application error")
    assert "ordinary application error" in caplog.text


def accepted_by_optional_decoder(value, image_count=2):
    decoder = pytest.importorskip("lmformatenforcer")
    parser = decoder.JsonSchemaParser(inspection_schema(image_count))
    for character in json.dumps(value, separators=(",", ":")):
        if character not in parser.get_allowed_characters():
            return False
        parser = parser.add_character(character)
    return parser.can_end()


@pytest.mark.parametrize("count", [1, 2])
def test_optional_real_parser_accepts_unknown_and_complete_revision_pair(count):
    value = output()
    assert accepted_by_optional_decoder(value, count)
    assert parse_output(json.dumps(value), image_count=count).candidates[0].revision is None
    value["candidates"][0].update(revision="A", revision_marking="REV A")
    assert accepted_by_optional_decoder(value, count)
    assert parse_output(json.dumps(value), image_count=count).candidates[0].revision == "A"
    value["candidates"] = []
    assert accepted_by_optional_decoder(value, count)


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(authority="approved"),
    lambda value: value.pop("uncertainties"),
    lambda value: value.update(uncertainties=[]),
    lambda value: value.update(uncertainties=["a", "b", "c"]),
    lambda value: value["observations"][0].update(image_indices=[]),
    lambda value: value["observations"][0].update(image_indices=[3]),
    lambda value: value["observations"][0].update(text=""),
    lambda value: value["observations"][0].update(text="x" * 161),
    lambda value: value["observations"][0].update(kind="functional"),
    lambda value: value["observations"][0].update(confidence=0.99),
    lambda value: value["candidates"][0].pop("image_indices"),
    lambda value: value["candidates"][0].update(revision="A", revision_marking=None),
    lambda value: value["candidates"][0].update(revision=None, revision_marking="REV A"),
    lambda value: value["candidates"].append(copy.deepcopy(value["candidates"][0])),
])
def test_optional_real_parser_rejects_invalid_shape_and_revision_pairs(mutation):
    value = output()
    mutation(value)
    assert not accepted_by_optional_decoder(value)


def test_optional_decoder_bounds_one_image_and_domain_rejects_duplicate_source_indices():
    value = output()
    value["observations"][0]["image_indices"] = [2]
    assert not accepted_by_optional_decoder(value, 1)
    value["observations"][0]["image_indices"] = [1, 1]
    # This known decoder limitation is intentionally not a relaxed domain rule.
    with pytest.raises(ValueError):
        parse_output(json.dumps(value), image_count=2)


@pytest.mark.parametrize("raw", ['{"observations":', '{"observations":[],"observations":[]}', ''])
def test_eos_or_truncation_does_not_repair_or_accept_invalid_output(raw):
    with pytest.raises(ValueError):
        parse_output(raw, image_count=1)


def test_optional_real_decoder_exception_redacts_prefix_and_eos_is_not_repaired(monkeypatch, caplog):
    decoder = pytest.importorskip("lmformatenforcer")
    from lmformatenforcer.tokenenforcer import TokenEnforcer, TokenEnforcerTokenizerData

    _protect_decoder_logs()
    secret = "PRIVATE IMAGE TEXT AND PROMPT"
    data = TokenEnforcerTokenizerData([(0, "a", False)], lambda tokens: secret, 1, False, 2)
    enforcer = TokenEnforcer(data, decoder.JsonSchemaParser(inspection_schema(1)))

    def fail(*args):
        raise RuntimeError(secret)

    monkeypatch.setattr(enforcer, "_collect_allowed_tokens", fail)
    assert enforcer.get_allowed_tokens([0]).allowed_tokens == [1]
    assert "Structured decoder" in caplog.text
    assert secret not in caplog.text
    # The library's emergency EOS is a stop, not permission to finish JSON.
    with pytest.raises(ValueError):
        parse_output('{"observations":', image_count=1)
