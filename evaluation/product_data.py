"""Source manifests and independent review for a small local product-image set.

Metadata describes the source listing. It is never a visible-truth annotation.
This module does not fetch images, execute models, or create inventory records.
"""

import argparse
from datetime import datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit
import warnings

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator


MAX_IMAGE_BYTES = 10 * 1024**2
MAX_COLLECTION_BYTES = 200 * 1024**2
MAX_METADATA_BYTES = 150 * 1024**2
MAX_MANIFEST_BYTES = 2 * 1024**2
Identifier = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
ImageId = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9+-]+$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=2000, pattern=r"^\S(?:[\s\S]*\S)?$")]
Notes = Annotated[str, StringConstraints(max_length=4000)]


def _aware_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Timestamp must be ISO 8601 with a timezone") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value


def _https_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Source references must be HTTPS URLs without credentials or fragments")
    if any(character.isspace() for character in value):
        raise ValueError("Source URL cannot contain whitespace")
    return value


Timestamp = Annotated[str, StringConstraints(min_length=1, max_length=64), AfterValidator(_aware_timestamp)]
SourceURL = Annotated[str, StringConstraints(min_length=1, max_length=2048), AfterValidator(_https_url)]


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def split_for_group(group_id: str) -> Literal["development", "holdout"]:
    """Keep every view of one listing in one stable evaluation group."""
    if not isinstance(group_id, str) or not group_id.strip():
        raise ValueError("A nonblank listing group is required")
    bucket = int(hashlib.sha256(group_id.encode("utf-8")).hexdigest()[:8], 16) % 5
    return "holdout" if bucket == 0 else "development"


class MetadataReceipt(_Contract):
    url: SourceURL
    bytes: Annotated[int, Field(gt=0, le=MAX_METADATA_BYTES)]
    sha256: Sha256


class ProductImage(_Contract):
    image_id: ImageId
    listing_id: Identifier
    group_id: Identifier
    split: Literal["development", "holdout"]
    source_url: SourceURL
    local_path: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    sha256: Sha256
    byte_size: Annotated[int, Field(gt=0, le=MAX_IMAGE_BYTES)]
    width: Annotated[int, Field(gt=0, le=8192)]
    height: Annotated[int, Field(gt=0, le=8192)]
    category: Text
    source_labels: dict[Identifier, Annotated[str, StringConstraints(max_length=4000)]] = Field(max_length=32)
    downloaded_at: Timestamp
    marking_visible: None = None
    exact_identity_visually_established: None = None
    revision_supported: None = None
    ambiguity_notes: Notes = ""
    review_status: Literal["pending"] = "pending"

    @model_validator(mode="after")
    def image_contract(self) -> Self:
        if self.group_id != self.listing_id:
            raise ValueError("The listing ID must be the evaluation group")
        if self.split != split_for_group(self.group_id):
            raise ValueError("All listing views must use the deterministic group split")
        if self.local_path != f"images/{self.image_id}.jpg":
            raise ValueError("Local image paths must be derived from the image ID")
        if self.width * self.height > 16_000_000:
            raise ValueError("Image exceeds the existing inspection pixel limit")
        return self


class DatasetManifest(_Contract):
    schema_version: Literal["rekit-real-products-v1"] = "rekit-real-products-v1"
    dataset: Literal["amazon-berkeley-objects"] = "amazon-berkeley-objects"
    source_url: SourceURL
    license_id: Literal["CC-BY-4.0"] = "CC-BY-4.0"
    license_url: SourceURL
    attribution: Text
    downloaded_at: Timestamp
    metadata_receipts: list[MetadataReceipt] = Field(max_length=32)
    images: list[ProductImage] = Field(max_length=60)

    @model_validator(mode="after")
    def unique_bounded_collection(self) -> Self:
        for field in ("image_id", "local_path", "sha256"):
            values = [getattr(image, field) for image in self.images]
            if len(set(values)) != len(values):
                raise ValueError(f"Duplicate image {field} is not a distinct evaluation example")
        if len({receipt.url for receipt in self.metadata_receipts}) != len(self.metadata_receipts):
            raise ValueError("Metadata receipt URLs must be unique")
        if sum(image.byte_size for image in self.images) > MAX_COLLECTION_BYTES:
            raise ValueError("Product images exceed the 200 MiB collection limit")
        if sum(receipt.bytes for receipt in self.metadata_receipts) > MAX_METADATA_BYTES:
            raise ValueError("Metadata exceeds the 150 MiB download limit")
        return self


def _read_json(path: Path) -> str:
    with Path(path).open("rb") as source:
        raw = source.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Evaluation JSON exceeds its 2 MiB limit")
    return raw.decode("utf-8")


def load_manifest(path: Path) -> DatasetManifest:
    return DatasetManifest.model_validate_json(_read_json(path))


def _manifest_copy(manifest: DatasetManifest) -> DatasetManifest:
    # Revalidate nested values, including mutated or construct/copy-created models.
    return DatasetManifest.model_validate_json(manifest.model_dump_json(warnings=False))


def verify_images(manifest: DatasetManifest, root: Path) -> dict:
    """Check the original local bytes and decode them; never fetch source URLs."""
    from PIL import Image, UnidentifiedImageError

    manifest = _manifest_copy(manifest)
    root = Path(root).absolute()
    if root.is_symlink() or root.is_junction():
        raise ValueError("Evaluation image root cannot be a link or junction")
    resolved_root = root.resolve()
    for item in manifest.images:
        path = root / item.local_path
        if any(part.is_symlink() or part.is_junction() for part in (path.parent, path)):
            raise ValueError("Evaluation images cannot traverse links or junctions")
        if not path.resolve().is_relative_to(resolved_root) or not path.is_file():
            raise ValueError(f"Missing or uncontained image: {item.image_id}")
        if path.stat().st_size != item.byte_size:
            raise ValueError(f"Image byte count changed: {item.image_id}")
        with path.open("rb") as source:
            raw = source.read(MAX_IMAGE_BYTES + 1)
        if len(raw) != item.byte_size or hashlib.sha256(raw).hexdigest() != item.sha256:
            raise ValueError(f"Image integrity check failed: {item.image_id}")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as image:
                    if image.format != "JPEG" or getattr(image, "n_frames", 1) != 1:
                        raise ValueError("The collection accepts original static JPEG images only")
                    if image.size != (item.width, item.height):
                        raise ValueError(f"Image dimensions changed: {item.image_id}")
                    image.load()
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as error:
            raise ValueError(f"Image could not be safely decoded: {item.image_id}") from error
    return {"status": "verified" if manifest.images else "missing_data", "images": len(manifest.images),
            "groups": len({item.group_id for item in manifest.images}),
            "byte_size": sum(item.byte_size for item in manifest.images),
            "reviewed": 0, "pending": len(manifest.images),
            "splits": {split: sum(item.split == split for item in manifest.images)
                       for split in ("development", "holdout")}}


class ReviewEntry(_Contract):
    image_id: ImageId
    sha256: Sha256
    review_status: Literal["pending", "reviewed"] = "pending"
    reviewer: Text | None = None
    reviewed_at: Timestamp | None = None
    independent_human_review: bool = False
    visible_markings: list[Text] = Field(default_factory=list, max_length=32)
    marking_visible: bool | None = None
    exact_identity_visually_established: bool | None = None
    identity_label: Text | None = None
    revision_supported: bool | None = None
    revision_label: Text | None = None
    support_notes: Notes = ""
    ambiguity_notes: Notes = ""

    @model_validator(mode="after")
    def reviewed_truth(self) -> Self:
        facts = (self.marking_visible, self.exact_identity_visually_established, self.revision_supported)
        if self.review_status == "pending":
            if (self.independent_human_review or self.reviewer is not None or self.reviewed_at is not None
                    or any(fact is not None for fact in facts) or self.visible_markings
                    or self.identity_label is not None or self.revision_label is not None):
                raise ValueError("Pending reviews cannot assert human-reviewed visual truth")
            return self
        if (not self.independent_human_review or self.reviewer is None or self.reviewed_at is None
                or any(fact is None for fact in facts) or not self.support_notes.strip()):
            raise ValueError("Reviewed labels require an independent human, time, explicit facts and support notes")
        if self.exact_identity_visually_established != (self.identity_label is not None):
            raise ValueError("An identity label requires explicit visible support")
        if self.revision_supported != (self.revision_label is not None):
            raise ValueError("A revision label requires explicit independent support")
        if not self.marking_visible and self.visible_markings:
            raise ValueError("Invisible markings cannot have a transcription")
        if self.revision_supported and (not self.marking_visible or not self.visible_markings):
            raise ValueError("Supported revision labels require readable visible markings")
        if len(set(self.visible_markings)) != len(self.visible_markings):
            raise ValueError("Visible marking transcriptions must be distinct")
        return self


class ReviewLedger(_Contract):
    schema_version: Literal["rekit-real-product-reviews-v1"] = "rekit-real-product-reviews-v1"
    reviews: list[ReviewEntry] = Field(max_length=60)

    @model_validator(mode="after")
    def unique_reviews(self) -> Self:
        if len({entry.image_id for entry in self.reviews}) != len(self.reviews):
            raise ValueError("Each image has at most one current review")
        return self


def validate_reviews(ledger: ReviewLedger, manifest: DatasetManifest) -> dict:
    manifest = _manifest_copy(manifest)
    ledger = ReviewLedger.model_validate_json(ledger.model_dump_json(warnings=False))
    sources = {item.image_id: item for item in manifest.images}
    for entry in ledger.reviews:
        if entry.image_id not in sources or entry.sha256 != sources[entry.image_id].sha256:
            raise ValueError("Review must reference the exact original image ID and hash")
    reviewed = sum(entry.review_status == "reviewed" for entry in ledger.reviews)
    return {"reviewed": reviewed, "pending": len(manifest.images) - reviewed,
            "accuracy_denominator_images": reviewed}


def load_reviews(path: Path, manifest: DatasetManifest) -> ReviewLedger:
    ledger = ReviewLedger.model_validate_json(_read_json(path))
    validate_reviews(ledger, manifest)
    return ledger


def review_template(manifest: DatasetManifest) -> ReviewLedger:
    manifest = _manifest_copy(manifest)
    return ReviewLedger(reviews=[ReviewEntry(image_id=item.image_id, sha256=item.sha256)
                                 for item in manifest.images])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Verify local bytes; never download or infer")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--root", type=Path, required=True)
    check.add_argument("--reviews", type=Path)
    template = commands.add_parser("review-template", help="Create a pending review ledger without overwriting one")
    template.add_argument("--manifest", type=Path, required=True)
    template.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.command == "check":
            result = verify_images(manifest, args.root)
            if args.reviews:
                result.update(validate_reviews(load_reviews(args.reviews, manifest), manifest))
        else:
            ledger = review_template(manifest)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(ledger.model_dump_json(indent=2) + "\n")
            result = {"status": "created", "pending": len(ledger.reviews), "reviewed": 0}
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
