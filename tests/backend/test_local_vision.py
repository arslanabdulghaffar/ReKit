"""CPU-only input/failure checks; these tests do not establish model accuracy."""

from importlib.util import module_from_spec, spec_from_file_location
import io
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

from rekit.inference.adapters.local_transformers import (
    LocalTransformersVision, LocalVisionBusy, LocalVisionError, _decode_images,
)


ROOT = Path(__file__).parents[2]
specification = spec_from_file_location("rekit_vision_smoke", ROOT / "evaluation" / "run_vision_smoke.py")
smoke = module_from_spec(specification)
specification.loader.exec_module(smoke)


def picture(*, format="PNG", size=(32, 24), color="red") -> bytes:
    with Image.new("RGB", size, color) as image:
        with io.BytesIO() as buffer:
            image.save(buffer, format=format)
            return buffer.getvalue()


@pytest.mark.parametrize("format", ["JPEG", "PNG", "WEBP"])
def test_supported_images_are_fully_decoded_and_bounded(format):
    images = _decode_images([picture(format=format, size=(1000, 500))])
    assert len(images) == 1
    assert images[0].mode == "RGB"
    assert images[0].size == (768, 384)
    images[0].load()


def test_two_views_remain_two_decoded_inputs():
    decoded = _decode_images([picture(color="red"), picture(color="blue")])
    assert len(decoded) == 2
    assert decoded[0].getpixel((0, 0)) != decoded[1].getpixel((0, 0))


@pytest.mark.parametrize("images", [[], [b"bad image"], [b""], [b"a"] * 3, [b"x" * (10 * 1024 * 1024 + 1)]])
def test_invalid_image_count_content_and_encoded_size_fail(images):
    with pytest.raises(LocalVisionError):
        _decode_images(images)


@pytest.mark.parametrize("size", [(8193, 1), (5000, 3400)])
def test_decoded_image_dimension_and_pixel_limits(size):
    with pytest.raises(LocalVisionError):
        _decode_images([picture(size=size)])


def test_unsupported_and_animated_images_fail():
    with pytest.raises(LocalVisionError):
        _decode_images([picture(format="BMP")])
    with io.BytesIO() as buffer:
        frames = [Image.new("RGB", (20, 20), color) for color in ("red", "blue")]
        try:
            frames[0].save(buffer, format="PNG", save_all=True, append_images=frames[1:], duration=50)
            content = buffer.getvalue()
        finally:
            for frame in frames:
                frame.close()
    with pytest.raises(LocalVisionError):
        _decode_images([content])


def test_imports_need_no_torch_transformers_or_cuda():
    script = """
import importlib.abc
import sys
class BlockModelRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'torchvision', 'transformers'}:
            raise AssertionError('Default backend import attempted model runtime: ' + fullname)
sys.meta_path.insert(0, BlockModelRuntime())
from rekit.inference.adapters.local_transformers import LocalTransformersVision
from rekit.main import app
assert '/health' in app.openapi()['paths']
assert 'torch' not in sys.modules and 'transformers' not in sys.modules
print('lightweight imports passed')
"""
    completed = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True,
                               text=True, timeout=30, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "lightweight imports passed"


def test_concurrent_request_fails_busy_without_loading(tmp_path, monkeypatch):
    provider = LocalTransformersVision(tmp_path)
    monkeypatch.setattr(provider, "_load", lambda: pytest.fail("busy request attempted model loading"))
    assert provider._lock.acquire(blocking=False)
    try:
        with pytest.raises(LocalVisionBusy):
            provider.inspect([picture()], "Describe this image.")
    finally:
        provider._lock.release()


def test_unavailable_gpu_fails_explicitly_and_releases_request_lock(tmp_path, monkeypatch):
    provider = LocalTransformersVision(tmp_path)

    def unavailable():
        raise LocalVisionError("CUDA is unavailable; CPU fallback is prohibited")

    monkeypatch.setattr(provider, "_load", unavailable)
    with pytest.raises(LocalVisionError, match="CUDA is unavailable"):
        provider.inspect([picture()], "Describe this image.")
    assert provider._lock.acquire(blocking=False)
    provider._lock.release()


def test_incomplete_local_verification_receipt_cannot_claim_a_pinned_model(tmp_path):
    from rekit.inference.adapters.local_transformers import MODEL_ID, MODEL_REVISION

    (tmp_path / "rekit-download.json").write_text(json.dumps({
        "model_id": MODEL_ID, "revision": MODEL_REVISION, "files": [],
    }), encoding="utf-8")
    with pytest.raises(LocalVisionError, match="Verified pinned model files are unavailable"):
        LocalTransformersVision(tmp_path)._verify_files()


@pytest.mark.parametrize("configuration", [
    {"device": -1}, {"device": True}, {"device": "1"},
    {"max_new_tokens": 0}, {"max_new_tokens": 513}, {"max_new_tokens": True},
    {"timeout_seconds": 0}, {"timeout_seconds": 121},
])
def test_invalid_device_token_and_time_bounds_are_rejected(tmp_path, configuration):
    with pytest.raises(ValueError):
        LocalTransformersVision(tmp_path, **configuration)


@pytest.mark.parametrize("prompt", ["", " " * 4, "x" * 12001])
def test_invalid_prompt_is_rejected_before_loading(tmp_path, monkeypatch, prompt):
    provider = LocalTransformersVision(tmp_path)
    monkeypatch.setattr(provider, "_load", lambda: pytest.fail("invalid prompt attempted model loading"))
    with pytest.raises(LocalVisionError):
        provider.inspect([picture()], prompt)


def test_smoke_records_failure_without_fabricating_a_run(tmp_path, monkeypatch):
    import rekit.inference.adapters.local_transformers as adapter

    class UnavailableProvider:
        def __init__(self, **configuration):
            pass

        def inspect(self, images, prompt):
            raise LocalVisionError("controlled unavailable test double")

    monkeypatch.setattr(adapter, "LocalTransformersVision", UnavailableProvider)
    output = tmp_path / "qualification.json"
    assert smoke.run(model_dir=tmp_path, device=1, output=output, image=None, repeat=2) == 1
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert record["synthetic"] is True
    assert record["runs"] == []
    assert record["error"]["type"] == "LocalVisionError"
    with Image.open(output.with_suffix(".png")) as image:
        assert image.size == (768, 512)


@pytest.mark.parametrize("patch", [
    {"device": "cpu"}, {"status": "failed"}, {"text": " "},
    {"metrics": {"image_tensor_shape": [], "vision_forward_calls": 1, "input_sha256": ["hash"]}},
    {"metrics": {"image_tensor_shape": [1, 3], "vision_forward_calls": 0, "input_sha256": ["hash"]}},
    {"metrics": {"image_tensor_shape": [1, 3], "vision_forward_calls": 1, "input_sha256": ["other"]}},
])
def test_smoke_rejects_missing_gpu_or_image_execution_evidence(patch):
    result = {"status": "succeeded", "device": "cuda:1", "text": "test double output",
              "metrics": {"image_tensor_shape": [1, 3], "vision_forward_calls": 1, "input_sha256": ["hash"]}}
    result.update(patch)
    with pytest.raises(RuntimeError):
        smoke._verify_image_execution(result, "hash", 1)
