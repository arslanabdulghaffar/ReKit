"""Acquire a bounded ABO sample from official objects, never image archives."""

import argparse
from collections import Counter
import csv
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/"
METADATA_LIMIT = 150 * 1024**2
IMAGE_LIMIT = 200 * 1024**2
MAX_RECORD_BYTES = 2 * 1024**2
MAX_DECODED_BYTES = 128 * 1024**2
MAX_PROJECTION_BYTES = 8 * 1024**2
ATTRIBUTION = (
    "Amazon Berkeley Objects data and images (c) Amazon.com, CC BY 4.0. "
    "Dataset builders: Matthieu Guillaumin, Thomas Dideriksen, Kenan Deng, Himanshu Arora, "
    "Arnab Dhua, Xi (Brian) Zhang, Tomas Yago-Vicente, Jasmine Collins, Shubham Goel, "
    "and Jitendra Malik. Original downloaded bytes are unchanged."
)
CATEGORIES = {
    "power_accessories": r"charger|power adapter|ac adapter|charging station|power strip|surge protector",
    "computer_interfaces": r"usb hub|usb.*adapter|adapter.*usb|card reader|docking station|ethernet adapter",
    "cables_connectors": r"cable|connector|power cord|extension cord",
    "tool_accessories": r"drill bit|screwdriver bit|socket set|socket adapter|hex key|wrench set",
    "household_parts": r"replacement filter|vacuum.*filter|replacement.*brush|replacement.*blade|faucet|shower head",
    "small_electronics": r"computer mouse|wireless mouse|wired mouse|remote control|webcam|headphone|earbud|speaker",
}


def timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("ABO downloads must not redirect to another destination")


class Downloader:
    """Bound actual bytes and verify cached receipts; never silently redownload."""

    def __init__(self, root: Path, *, cached_only: bool = False):
        self.root = root.resolve()
        if not self.root.is_relative_to((ROOT / "var").resolve()):
            raise ValueError("Evaluation assets must stay inside ignored repository var storage")
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.root / "download-ledger.json"
        self.receipts = json.loads(self.ledger_path.read_text(encoding="utf-8")) if self.ledger_path.exists() else {}
        self.transfer_path = self.root / "transfer-bytes.json"
        completed = {kind: sum(item["bytes"] for item in self.receipts.values() if item["kind"] == kind)
                     for kind in ("metadata", "image")}
        self.transferred = json.loads(self.transfer_path.read_text(encoding="utf-8")) if self.transfer_path.exists() else completed
        if (set(self.transferred) != set(completed)
                or any(type(value) is not int or value < completed[kind] for kind, value in self.transferred.items())):
            raise ValueError("Download byte ledger is invalid")
        self.opener = urllib.request.build_opener(NoRedirect())
        self.cached_only = cached_only

    def fetch(self, relative: str, local: str, *, kind: str, maximum: int) -> dict:
        if kind not in ("metadata", "image") or not re.fullmatch(r"[A-Za-z0-9_/.-]+", relative) or ".." in relative:
            raise ValueError("Invalid official object path or download kind")
        target = (self.root / local).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Download path escaped evaluation storage")
        url = BASE + relative
        previous = self.receipts.get(url)
        if previous:
            if target.stat().st_size != previous["bytes"] or target.stat().st_size > maximum:
                raise ValueError("Cached download byte count changed or exceeds its bound")
            raw = target.read_bytes()
            if (previous["local"] != local or previous["kind"] != kind or len(raw) != previous["bytes"]
                    or hashlib.sha256(raw).hexdigest() != previous["sha256"] or len(raw) > maximum):
                raise ValueError("Cached download no longer matches its original receipt")
            return previous
        if target.exists():
            raise ValueError("Refusing to overwrite an unreceipted local file")
        if self.cached_only:
            raise ValueError("Cached-only acquisition is missing a verified object")
        ceiling = METADATA_LIMIT if kind == "metadata" else IMAGE_LIMIT
        used = self.transferred[kind]
        bound = min(maximum, ceiling - used)
        if bound <= 0:
            raise ValueError("Cumulative acquisition budget is exhausted")
        request = urllib.request.Request(url, headers={"User-Agent": "ReKit-bounded-evaluation", "Accept-Encoding": "identity"})
        chunks, total = [], 0
        try:
            with self.opener.open(request, timeout=45) as response:
                length = response.headers.get("Content-Length")
                if response.status != 200 or (length is not None and not 0 < int(length) <= bound):
                    raise ValueError("Official object exceeds its download bound or returned unexpected status")
                while total < bound:
                    chunk = response.read(min(64 * 1024, bound - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > bound:
                        raise ValueError("Actual download exceeded the bounded byte budget")
                    chunks.append(chunk)
                if (length is not None and total != int(length)) or (total == bound and length is None):
                    raise ValueError("Download length differs from its header or cannot be bounded safely")
                raw = b"".join(chunks)
        finally:
            # Failed partial transfers still consume the mission acquisition budget.
            self.transferred[kind] += total
            self.transfer_path.write_text(json.dumps(self.transferred, indent=2) + "\n", encoding="utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        receipt = {"url": url, "local": local, "kind": kind, "bytes": total,
                   "sha256": hashlib.sha256(raw).hexdigest(), "downloaded_at": timestamp()}
        self.receipts[url] = receipt
        self.ledger_path.write_text(json.dumps(self.receipts, indent=2) + "\n", encoding="utf-8")
        print(f"Downloaded {relative}: {total} bytes", flush=True)
        return receipt


def source_text(record: dict, key: str) -> str:
    values = record.get(key, [])
    if isinstance(values, str):
        return values[:1000]
    if not isinstance(values, list):
        return ""
    english = [value for value in values if isinstance(value, dict) and value.get("language_tag") == "en_US"]
    plain = [value for value in values if isinstance(value, dict) and "language_tag" not in value]
    return "; ".join(str(value.get("value", "")) for value in english or plain)[:1000]


def category_for(title: str) -> str | None:
    for category, pattern in CATEGORIES.items():
        if re.search(pattern, title, flags=re.IGNORECASE):
            return category
    return None


def metadata(downloader: Downloader) -> list[dict]:
    receipts = []
    for relative in ("LICENSE-CC-BY-4.0.txt", "README.md", "images/README.md", "listings/README.md"):
        receipts.append(downloader.fetch(relative, "metadata/" + relative.replace("/", "-"), kind="metadata", maximum=1024**2))
    for digit in "0123456789abcdef":
        relative = f"listings/metadata/listings_{digit}.json.gz"
        receipts.append(downloader.fetch(relative, f"metadata/listings_{digit}.json.gz", kind="metadata", maximum=15 * 1024**2))
    receipts.append(downloader.fetch("images/metadata/images.csv.gz", "metadata/images.csv.gz", kind="metadata", maximum=15 * 1024**2))
    return receipts


def parse_shard(path: Path) -> dict:
    """Read one shard using only the standard library; never write source data."""
    if path.stat().st_size > 15 * 1024**2:
        raise ValueError("Compressed shard exceeds its bound")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    records, decoded_bytes, projected_bytes, selected = 0, 0, 0, []
    with gzip.open(path, "rb") as stream:
        while raw := stream.readline(MAX_RECORD_BYTES + 1):
            records += 1
            decoded_bytes += len(raw)
            if len(raw) > MAX_RECORD_BYTES or decoded_bytes > MAX_DECODED_BYTES:
                raise ValueError(f"Shard bounds exceeded: {path.name}:{records}")
            try:
                item = json.loads(raw.decode("utf-8"))
            except (UnicodeError, ValueError) as error:
                raise ValueError(f"Invalid listing JSON: {path.name}:{records}") from error
            if not isinstance(item, dict):
                raise ValueError(f"Listing is not an object: {path.name}:{records}")
            title = source_text(item, "item_name")
            category = category_for(title)
            if category and re.fullmatch(r"[A-Za-z0-9_-]+", item.get("item_id", "")):
                views = item.get("other_image_id", [])
                if not isinstance(views, list) or len(views) > 1024 or any(not isinstance(v, str) or len(v) > 128 for v in views):
                    raise ValueError(f"Invalid listing image references: {path.name}:{records}")
                compact = {key: source_text(item, key) for key in ("item_name", "product_type", "brand", "model_number")}
                compact.update({key: item.get(key, "") for key in ("item_id", "domain_name", "main_image_id")})
                compact.update(other_image_id=views, metadata_shard=path.name, metadata_line=records)
                row = {"category": category, "item": compact}
                projected_bytes += len(json.dumps(row, ensure_ascii=True).encode("utf-8"))
                if projected_bytes > MAX_PROJECTION_BYTES - 1024:
                    raise ValueError("Shard projection exceeds its bound")
                selected.append(row)
    return {"shard": path.name, "sha256": digest, "records": records,
            "decoded_bytes": decoded_bytes, "selected": selected}


def isolated_shard(path: Path) -> dict:
    """A failed child cannot modify receipts or become a successful selection."""
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-X", "utf8", "-X", "faulthandler",
             str(Path(__file__).resolve()), "--parse-shard", str(path.resolve())],
            capture_output=True, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"Metadata child timed out: {path.name}") from error
    if result.returncode:
        diagnostic = result.stderr.decode("utf-8", errors="replace")[-2000:]
        raise ValueError(f"Metadata child failed: {path.name}, exit={result.returncode}; {diagnostic}")
    if len(result.stdout) > MAX_PROJECTION_BYTES:
        raise ValueError("Metadata child output exceeds its bound")
    data = json.loads(result.stdout)
    if (not isinstance(data, dict) or set(data) != {"shard", "sha256", "records", "decoded_bytes", "selected"}
            or data["shard"] != path.name or data["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
            or type(data["records"]) is not int or data["records"] < 0
            or type(data["decoded_bytes"]) is not int or not 0 <= data["decoded_bytes"] <= MAX_DECODED_BYTES
            or not isinstance(data["selected"], list) or len(data["selected"]) > data["records"]):
        raise ValueError("Invalid metadata child receipt")
    return data


def candidates(root: Path) -> tuple[dict, dict]:
    buckets = {category: {} for category in CATEGORIES}
    for digit in "0123456789abcdef":
        data = isolated_shard(root / f"metadata/listings_{digit}.json.gz")
        for row in data["selected"]:
            item, category = row["item"], row["category"]
            # Preserve original shard/line order and first marketplace record.
            buckets[category].setdefault(item["item_id"], item)
    wanted = {image_id for bucket in buckets.values() for item in bucket.values()
              for image_id in [item["main_image_id"], *item["other_image_id"]]}
    with gzip.open(root / "metadata/images.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        images = {}
        for row in csv.DictReader(stream):
            if row["image_id"] in wanted:
                if row["image_id"] in images:
                    raise ValueError("Duplicate image ID in official image index")
                images[row["image_id"]] = row
    return buckets, images


def prepare(root: Path, manifest_path: Path, *, metadata_only: bool = False, cached_only: bool = False) -> dict:
    if not metadata_only and manifest_path.exists():
        raise ValueError("Refusing to overwrite an existing selection manifest")
    downloader = Downloader(root, cached_only=cached_only)
    receipts = metadata(downloader)
    if metadata_only:
        return {"status": "metadata_ready", "bytes": sum(item["bytes"] for item in receipts)}
    buckets, index = candidates(downloader.root)
    # Native application dependencies load only after isolated metadata parsing.
    from product_data import DatasetManifest, split_for_group, verify_images
    from PIL import Image
    selected, seen_images, seen_hashes, chosen_listings = [], set(), set(), set()

    def add(item: dict, category: str, image_id: str, view: str) -> bool:
        if image_id not in [item.get("main_image_id", ""), *item.get("other_image_id", [])]:
            raise ValueError("Image does not belong to its source listing")
        row = index.get(image_id)
        if row is None or image_id in seen_images or not re.fullmatch(r"[A-Za-z0-9+-]+", image_id):
            return False
        width, height = int(row["width"]), int(row["height"])
        if min(width, height) < 250 or max(width, height) > 8192 or width * height > 16_000_000:
            return False
        if not re.fullmatch(r"[0-9a-f]{2}/[0-9a-f]+\.jpg", row["path"]):
            return False
        local = f"images/{image_id}.jpg"
        receipt = downloader.fetch("images/original/" + row["path"], local, kind="image", maximum=10 * 1024**2)
        if receipt["sha256"] in seen_hashes:
            return False
        with Image.open(downloader.root / local) as image:
            if image.format != "JPEG" or image.size != (width, height):
                raise ValueError("Downloaded image differs from official index dimensions or format")
            image.verify()
        selected.append({"image_id": image_id, "listing_id": item["item_id"], "group_id": item["item_id"],
                         "split": split_for_group(item["item_id"]), "source_url": receipt["url"], "local_path": local,
                         "sha256": receipt["sha256"], "byte_size": receipt["bytes"], "width": width, "height": height,
                         "category": category, "source_labels": {"item_name": source_text(item, "item_name"),
                         "product_type": source_text(item, "product_type"), "brand": source_text(item, "brand"),
                         "model_number": source_text(item, "model_number"), "domain_name": item.get("domain_name", ""),
                         "metadata_shard": item.get("metadata_shard", ""), "metadata_line": str(item.get("metadata_line", "")),
                         "view_selection": view, "image_kind": "Catalog image; capture origin not independently reviewed"},
                         "downloaded_at": receipt["downloaded_at"], "marking_visible": None,
                         "exact_identity_visually_established": None, "revision_supported": None,
                         "ambiguity_notes": "Source title/category/model are metadata, not visual proof. Inspect legibility, similar connectors and absent identifiers; independent human review is pending.",
                         "review_status": "pending"})
        seen_images.add(image_id)
        seen_hashes.add(receipt["sha256"])
        return True

    chosen = []
    for category, items in buckets.items():
        count = 0
        for listing_id in sorted(items, key=lambda value: hashlib.sha256(value.encode()).hexdigest()):
            if listing_id in chosen_listings:
                continue
            item = items[listing_id]
            views = [item.get("main_image_id", "")] + item.get("other_image_id", [])
            # Alternate views are intentionally included, before seeing model output.
            order = views[1:] + views[:1] if count % 2 else views
            for image_id in order:
                if add(item, category, image_id, "main" if image_id == views[0] else "alternate"):
                    count += 1
                    chosen_listings.add(listing_id)
                    chosen.append((item, category, views))
                    break
            if count == 8:
                break
        if count != 8:
            raise ValueError(f"Insufficient bounded selections for category {category}: {count}/8")
    # Four extra same-listing views support genuine joint-image evaluation.
    extras = 0
    for item, category, views in chosen:
        if any(add(item, category, image_id, "additional_same_listing") for image_id in views):
            extras += 1
        if extras == 4:
            break
    data = {"schema_version": "rekit-real-products-v1", "dataset": "amazon-berkeley-objects",
            "source_url": BASE + "index.html", "license_id": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/", "attribution": ATTRIBUTION,
            "downloaded_at": timestamp(), "metadata_receipts": [{key: receipt[key] for key in ("url", "bytes", "sha256")} for receipt in receipts],
            "images": selected}
    manifest = DatasetManifest.model_validate(data)
    summary = verify_images(manifest, downloader.root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n")
    return {**summary, "categories": dict(Counter(item["category"] for item in selected)),
            "metadata_bytes": sum(item["bytes"] for item in receipts),
            "downloaded_image_bytes": sum(item["bytes"] for item in downloader.receipts.values() if item["kind"] == "image")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "var/evaluation/abo")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/fixtures/abo-manifest.json")
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--cached-only", action="store_true")
    parser.add_argument("--parse-shard", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.parse_shard:
        print(json.dumps(parse_shard(args.parse_shard), ensure_ascii=True))
    else:
        print(json.dumps(prepare(args.root, args.manifest, metadata_only=args.metadata_only, cached_only=args.cached_only), indent=2))
