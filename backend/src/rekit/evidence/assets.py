"""Bounded local image storage and immutable evidence provenance.

SQLite metadata and its observation commit together. Bytes are written and synced
first; a process crash can leave an unreferenced file, never a committed record
that intentionally points to a partially written file. Storage is server-owned.
"""

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Annotated, Literal, Self
from uuid import uuid4
import warnings

from PIL import Image, UnidentifiedImageError
from pydantic import AwareDatetime, Field, StringConstraints, TypeAdapter, model_validator

from rekit.catalog.models import CatalogModel, Identifier
from rekit.evidence.models import AssertionSource, Observation
from rekit.evidence.store import ConflictError, EvidenceStore, NotFoundError


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_SIDE = 8192
_FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}
_EXTENSIONS = {media: extension for media, extension in _FORMATS.values()}
_REFERENCE = re.compile(r"asset:(asset-[a-f0-9]{32})")
_IDENTIFIER = TypeAdapter(Identifier)


class AssetTooLargeError(ValueError):
    """The encoded image or its decoded dimensions exceed configured limits."""


class AssetUnsupportedError(ValueError):
    """The declared or actual media format is not an allowed image format."""


class AssetInvalidError(ValueError):
    """Image data or a managed asset reference is malformed."""


class AssetMissingError(ValueError):
    """A known asset no longer has its stored bytes."""


class AssetCorruptError(ConflictError):
    """Stored bytes no longer match immutable asset metadata."""


class AssetUnavailableError(ValueError):
    """Server-owned asset storage cannot be safely accessed."""


class AssetAvailability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    CORRUPT = "corrupt"
    UNAVAILABLE = "unavailable"


class ImageAsset(CatalogModel):
    asset_id: Annotated[str, StringConstraints(strict=True, pattern=r"^asset-[a-f0-9]{32}$")]
    physical_component_id: Identifier
    return_id: Identifier
    sha256: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
    byte_size: Annotated[int, Field(strict=True, gt=0, le=10 * 1024 * 1024)]
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    width: Annotated[int, Field(strict=True, gt=0, le=8192)]
    height: Annotated[int, Field(strict=True, gt=0, le=8192)]
    received_at: AwareDatetime
    uploaded_by: Identifier
    observation_id: Identifier
    availability: AssetAvailability = AssetAvailability.AVAILABLE

    @model_validator(mode="after")
    def bounded_dimensions(self) -> Self:
        if self.width * self.height > 16_000_000:
            raise ValueError("Image pixel count exceeds the supported limit")
        return self


class UploadResult(CatalogModel):
    asset: ImageAsset
    observation: Observation
    duplicate: Annotated[bool, Field(strict=True)]


_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS image_assets (
        asset_id TEXT PRIMARY KEY,
        physical_component_id TEXT NOT NULL REFERENCES physical_components(physical_component_id),
        return_id TEXT NOT NULL REFERENCES returns(return_id),
        sha256 TEXT NOT NULL UNIQUE,
        observation_id TEXT NOT NULL UNIQUE REFERENCES evidence_events(event_id),
        payload TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS image_assets_by_component ON image_assets(physical_component_id, asset_id)",
    """CREATE TRIGGER IF NOT EXISTS image_assets_no_update BEFORE UPDATE ON image_assets
        BEGIN SELECT RAISE(ABORT, 'Image asset metadata is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS image_assets_no_delete BEFORE DELETE ON image_assets
        BEGIN SELECT RAISE(ABORT, 'Image asset metadata is immutable'); END""",
)


def _linked(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _decode(raw: bytes, content_type: str) -> tuple[str, int, int]:
    if not isinstance(raw, bytes) or not raw:
        raise AssetInvalidError("A nonempty image byte payload is required")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AssetTooLargeError("Image exceeds the upload byte limit")
    if not isinstance(content_type, str):
        raise AssetUnsupportedError("A supported image Content-Type is required")
    declared = content_type.split(";", 1)[0].strip().lower()
    if declared not in _EXTENSIONS:
        raise AssetUnsupportedError("Only image/jpeg, image/png, and image/webp are supported")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw), formats=tuple(_FORMATS)) as image:
                media_type = _FORMATS[image.format][0]
                if media_type != declared:
                    raise AssetUnsupportedError("Image format does not match its Content-Type")
                width, height = image.size
                if width < 1 or height < 1:
                    raise AssetInvalidError("Image dimensions must be positive")
                if max(width, height) > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
                    raise AssetTooLargeError("Image exceeds the decoded dimension or pixel limit")
                if getattr(image, "is_animated", False) or getattr(image, "n_frames", 1) != 1:
                    raise AssetInvalidError("Animated and multi-frame images are not supported")
                image.verify()
            # verify() checks structure; a fresh decoder must also load every pixel.
            with Image.open(BytesIO(raw), formats=tuple(_FORMATS)) as decoded:
                decoded.load()
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise AssetTooLargeError("Image exceeds the safe decoded pixel limit") from None
    except (AssetTooLargeError, AssetUnsupportedError, AssetInvalidError):
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, OverflowError):
        raise AssetInvalidError("Image bytes could not be fully decoded") from None
    except MemoryError:
        raise AssetUnavailableError("Image decoding resources are unavailable") from None
    return media_type, width, height


class ImageAssetStore:
    """Concrete SQLite integration using EvidenceStore's shared transaction helpers."""

    def __init__(self, evidence: EvidenceStore, root: str | Path) -> None:
        self.evidence = evidence
        self.root = Path(root).absolute()
        try:
            self._check_root(require_exists=False)
            self.root.mkdir(parents=True, exist_ok=True)
            self.root = self.root.resolve(strict=True)
            self._check_root()
        except OSError:
            raise AssetUnavailableError("Image storage cannot be initialized") from None
        with self.evidence.transaction() as connection:
            for statement in _SCHEMA:
                connection.execute(statement)

    def _check_root(self, *, require_exists: bool = True) -> None:
        try:
            if any(_linked(path) for path in (self.root, *self.root.parents)):
                raise AssetUnavailableError("Image storage must not traverse symbolic links or junctions")
            if require_exists and (not self.root.is_dir() or self.root.resolve() != self.root):
                raise AssetUnavailableError("Image storage is unavailable")
        except OSError:
            raise AssetUnavailableError("Image storage cannot be safely accessed") from None

    def _path(self, asset: ImageAsset) -> Path:
        self._check_root()
        path = self.root / (asset.asset_id + _EXTENSIONS[asset.media_type])
        try:
            if path.parent != self.root or _linked(path):
                raise AssetUnavailableError("Image storage path is unsafe")
        except OSError:
            raise AssetUnavailableError("Image storage path cannot be safely accessed") from None
        return path

    @staticmethod
    def _metadata(connection: sqlite3.Connection, asset_id: str) -> ImageAsset:
        row = connection.execute("SELECT payload FROM image_assets WHERE asset_id = ?", (asset_id,)).fetchone()
        if row is None:
            raise NotFoundError("Unknown image asset")
        return ImageAsset.model_validate_json(row["payload"])

    def _read_bytes(self, asset: ImageAsset) -> bytes:
        try:
            path = self._path(asset)
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, "rb") as file:
                details = os.fstat(file.fileno())
                if not stat.S_ISREG(details.st_mode):
                    raise AssetUnavailableError("Image storage entry is not a regular file")
                if details.st_size != asset.byte_size:
                    raise AssetCorruptError("Image bytes do not match immutable metadata")
                raw = file.read(asset.byte_size + 1)
        except FileNotFoundError:
            raise AssetMissingError("Stored image bytes are missing") from None
        except OSError:
            raise AssetUnavailableError("Stored image bytes cannot be accessed") from None
        if len(raw) != asset.byte_size or sha256(raw).hexdigest() != asset.sha256:
            raise AssetCorruptError("Image bytes do not match immutable metadata")
        return raw

    def _availability(self, asset: ImageAsset) -> ImageAsset:
        try:
            self._read_bytes(asset)
            state = AssetAvailability.AVAILABLE
        except AssetMissingError:
            state = AssetAvailability.MISSING
        except AssetCorruptError:
            state = AssetAvailability.CORRUPT
        except AssetUnavailableError:
            state = AssetAvailability.UNAVAILABLE
        return asset.model_copy(update={"availability": state})

    def _duplicate(
        self, connection: sqlite3.Connection, digest: str, component_id: str
    ) -> UploadResult | None:
        row = connection.execute("SELECT payload FROM image_assets WHERE sha256 = ?", (digest,)).fetchone()
        if row is None:
            return None
        asset = ImageAsset.model_validate_json(row["payload"])
        if asset.physical_component_id != component_id:
            raise ConflictError("Identical image bytes already belong to a different physical component")
        self._read_bytes(asset)
        observation = self.evidence._observation(connection, asset.observation_id, component_id)
        return UploadResult(asset=asset, observation=observation, duplicate=True)

    def _write_new(self, asset: ImageAsset, raw: bytes) -> tuple[Path, tuple[int, int]]:
        path = self._path(asset)
        descriptor = None
        created = False
        written = False
        identity = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags, 0o600)
            created = True
            details = os.fstat(descriptor)
            identity = (details.st_dev, details.st_ino)
            with os.fdopen(descriptor, "wb") as file:
                descriptor = None
                file.write(raw)
                file.flush()
                os.fsync(file.fileno())
            written = True
            return path, identity
        except OSError:
            raise AssetUnavailableError("Image bytes could not be stored") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if created and identity is not None and not written:
                self._remove_new(path, identity)

    def _remove_new(self, path: Path, identity: tuple[int, int]) -> None:
        try:
            self._check_root()
            if _linked(path):
                return
            details = path.stat()
            if (details.st_dev, details.st_ino) == identity:
                path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            raise AssetUnavailableError("Uncommitted image bytes could not be cleaned up") from None

    def upload(
        self, component_id: str, return_id: str, raw: bytes, content_type: str,
        actor_id: str, source: AssertionSource = AssertionSource.OPERATOR,
    ) -> UploadResult:
        component_id = _IDENTIFIER.validate_python(component_id)
        return_id = _IDENTIFIER.validate_python(return_id)
        actor_id = _IDENTIFIER.validate_python(actor_id)
        source = AssertionSource(source)
        media_type, width, height = _decode(raw, content_type)
        digest = sha256(raw).hexdigest()
        with self.evidence._read() as connection:
            component = self.evidence._component(connection, component_id)
            if component.source_return_id != return_id:
                raise ConflictError("Image return does not match the physical component")
            duplicate = self._duplicate(connection, digest, component_id)
            if duplicate is not None:
                return duplicate
        now = datetime.now(UTC)
        asset = ImageAsset(
            asset_id=f"asset-{uuid4().hex}", physical_component_id=component_id,
            return_id=return_id, sha256=digest, byte_size=len(raw), media_type=media_type,
            width=width, height=height, received_at=now, uploaded_by=actor_id,
            observation_id=f"asset-observation-{uuid4().hex}",
        )
        observation = Observation(
            observation_id=asset.observation_id, physical_component_id=component_id,
            source_return_id=return_id, captured_at=now,
            evidence_reference=f"asset:{asset.asset_id}", source=source,
            source_reference=actor_id,
        )
        path, identity = self._write_new(asset, raw)
        persisted = False
        try:
            with self.evidence.transaction() as connection:
                component = self.evidence._component(connection, component_id)
                if component.source_return_id != return_id:
                    raise ConflictError("Image return does not match the physical component")
                result = self._duplicate(connection, digest, component_id)
                if result is None:
                    self.evidence._append(connection, observation.observation_id, "observation", observation)
                    payload = json.dumps(asset.model_dump(mode="json", exclude={"availability"}), sort_keys=True, separators=(",", ":"))
                    connection.execute(
                        "INSERT INTO image_assets(asset_id, physical_component_id, return_id, sha256, observation_id, payload) VALUES (?, ?, ?, ?, ?, ?)",
                        (asset.asset_id, component_id, return_id, digest, observation.observation_id, payload),
                    )
                    result = UploadResult(asset=asset, observation=observation, duplicate=False)
            persisted = not result.duplicate
            return result
        finally:
            if not persisted:
                self._remove_new(path, identity)

    def list_assets(self, component_id: str) -> tuple[ImageAsset, ...]:
        component_id = _IDENTIFIER.validate_python(component_id)
        with self.evidence._read() as connection:
            self.evidence._component(connection, component_id)
            return tuple(
                self._availability(ImageAsset.model_validate_json(row["payload"]))
                for row in connection.execute(
                    "SELECT payload FROM image_assets WHERE physical_component_id = ? ORDER BY asset_id", (component_id,)
                )
            )

    def metadata(self, asset_id: str) -> ImageAsset:
        asset_id = _IDENTIFIER.validate_python(asset_id)
        with self.evidence._read() as connection:
            return self._availability(self._metadata(connection, asset_id))

    def read(self, asset_id: str) -> tuple[ImageAsset, bytes]:
        asset_id = _IDENTIFIER.validate_python(asset_id)
        with self.evidence._read() as connection:
            asset = self._metadata(connection, asset_id)
            return asset, self._read_bytes(asset)

    def _assert_reference(self, connection: sqlite3.Connection, component_id: str, reference: str) -> None:
        if not isinstance(reference, str):
            raise AssetInvalidError("An evidence reference must be text")
        if not reference.strip().lower().startswith("asset:"):
            return
        match = _REFERENCE.fullmatch(reference)
        if match is None:
            raise AssetInvalidError("Managed image reference must use its canonical asset ID")
        asset = self._metadata(connection, match.group(1))
        if asset.physical_component_id != component_id:
            raise ConflictError("Image asset belongs to a different physical component")
        self._read_bytes(asset)

    def assert_observation_reference(self, component_id: str, reference: str) -> None:
        component_id = _IDENTIFIER.validate_python(component_id)
        with self.evidence._read() as connection:
            self.evidence._component(connection, component_id)
            self._assert_reference(connection, component_id, reference)

    def assert_current_assets(self, component_id: str) -> None:
        """Check assets cited by the latest verification, including one awaiting review."""
        component_id = _IDENTIFIER.validate_python(component_id)
        with self.evidence._read() as connection:
            history = self.evidence._history(connection, component_id)
            if history.current.verification is None:
                return
            for observation_id in history.current.verification.evidence_observation_ids:
                observation = self.evidence._observation(connection, observation_id, component_id)
                self._assert_reference(connection, component_id, observation.evidence_reference)
