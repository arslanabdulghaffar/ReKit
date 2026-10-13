# Real product image evaluation

Mission 04 uses a small Amazon Berkeley Objects (ABO) catalog-image collection to move beyond synthetic illustrations. Acquisition and file integrity do not establish recognition accuracy. The source manifest keeps every visual-truth field unknown and every image pending until a separate human review is recorded. Catalog images also require review for photographic, rendered, or composite content; they are not automatically evidence of returned physical components.

**Current status: Task 1 acquisition and integrity acceptance passed; commit/push is pending.** The separately authorized recovery reused 21 metadata objects (93,897,585 bytes) and 52 original image objects (9,809,702 bytes), without downloading them again. `evaluation/fixtures/abo-manifest.json` now records 52 images in 48 listing groups, including four additional same-listing views. Image splits are 34 development and 18 holdout. Source categories contain 12 power-accessory images and eight in each of the other five categories. Human-reviewed labels remain **0**; no recognition accuracy is claimed.

Contact-sheet triage found a logo-only image (`61OnkGVhMWL`), USB reference charts (`51aqijMk6hL` and `51a0DIkpJcL`), and composite imagery. This is a collection of 52 catalog images, **not 52 verified product photographs**. That observation does not complete independent ground-truth review; all 52 entries remain pending. Later inference must report this source-content limitation and identify any subset used for product-view examples.

Before changes, all six uncommitted source/documentation files and the existing crash/download records were backed up under `var/recovery/mission04-20261014-031112/`. Its `preservation.json` records file hashes and successful original-byte verification of all 73 cached objects. Approach A parsed each of the 16 listing shards in a fresh standard-library-only interpreter; all exited successfully. Two actual `--cached-only` finalizations exited 0, with every manifest field identical except the top-level finalization timestamp. Independent audits confirmed all 52 listing/image relationships, index URLs and dimensions, and original-byte hashes. The integrity CLI verified all images; the review template contains 52 pending entries. Updated acquisition tests passed 44 cases and the full backend suite passed 724. Commands and measurements are recorded in the [mission report](reports/development-mission-04.md).

The earlier stop remains part of the evidence. Initial finalization exposed a 16-receipt schema limit, corrected to 32, and official image IDs containing `+` now validate. Later attempts produced inconsistent JSON errors and a native access violation, Windows exit `0xC0000005` (`-1073741819`), in `json.decoder.raw_decode`; Windows recorded faults in `python312.dll`. Original crash evidence remains at `var/evaluation/abo/python-crash-events.json`. Isolation and lower metadata retention are a working mitigation, **not a proven root cause**. No Python, CUDA, driver or model package was replaced; no independent Node parser or additional recovery approach was needed.

## Source, license and attribution

Verified on October 14, 2026: the [official distribution](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html) and its [distributed license](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/LICENSE-CC-BY-4.0.txt) specify **CC BY 4.0**. The [AWS Open Data registry](https://registry.opendata.aws/amazon-berkeley-objects/) explicitly records the change from CC BY-NC to CC BY for all assets in 2023. Older noncommercial statements do not describe the current distribution.

Keep this credit with the collection and any shared examples:

> Amazon Berkeley Objects data and images © Amazon.com. Dataset builders: Matthieu Guillaumin, Thomas Dideriksen, Kenan Deng, Himanshu Arora, Arnab Dhua, Xi (Brian) Zhang, Tomas Yago-Vicente, Jasmine Collins, Shubham Goel, and Jitendra Malik. Licensed under CC BY 4.0. Original downloaded bytes are unchanged.

Link the [source](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html) and [license](https://creativecommons.org/licenses/by/4.0/), retain supplied notices, and identify any later crops, resizes, overlays or other modifications when sharing them. Attribution must not imply endorsement; additional restrictions must not remove permissions the license grants. The official distribution also requests its CVPR 2022 paper citation for publications: *ABO: Dataset and Benchmarks for Real-World 3D Object Understanding*, Collins et al.

## Bounded acquisition

[prepare_abo.py](../evaluation/prepare_abo.py) uses individual public HTTPS objects under `https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/`. The distribution documents direct S3 access using the archive directory structure; the [image README](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/images/README.md) describes the image index and original-image paths. No AWS credentials, image archives, 3D packages, retail scraping, or model execution are needed.

| Objects | Purpose | Bound |
| --- | --- | --- |
| License and three READMEs | Provenance and retrieval documentation | 1 MiB each |
| `listings/metadata/listings_0.json.gz` through `listings_f.json.gz` | Listing IDs, titles and image associations | 15 MiB per compressed shard |
| `images/metadata/images.csv.gz` | Image ID, dimensions and relative JPEG path | 15 MiB |
| `images/original/<path from image index>` | Selected original catalog images | 10 MiB per image |

The cumulative transfer ceilings are **150 MiB metadata** and **200 MiB images**, including bytes read during failed partial transfers. Official receipts total 93,897,585 metadata bytes and 9,809,702 image bytes. The receipts preserve each source URL, exact byte count and SHA-256. These counts do not imply independent visual review.

The script selects eight distinct listing groups in each of six metadata-based categories: power accessories, computer interfaces, cables/connectors, tool accessories, household parts and small electronics. Four additional same-listing views give a target of 52 images across 48 listing groups. Main and alternate views are alternated before model results exist. Images must be JPEGs, at least 250 pixels on each side, at most 8192 pixels on either side and at most 16 million pixels. Duplicate image IDs and identical image hashes are excluded. Category words and source model numbers guide selection; they do not establish what can be read or identified in a photograph.

The recovery path verifies and reuses the existing cache. `--cached-only` refuses a missing receipt before any network request. Run from the repository root in the existing environment:

```powershell
.venv\Scripts\python.exe evaluation\product_data.py check --manifest evaluation\fixtures\abo-manifest.json --root var\evaluation\abo
.venv\Scripts\python.exe evaluation\prepare_abo.py --cached-only --manifest var\evaluation\abo\selection-repeat.json
```

The default image/metadata root is ignored `var/evaluation/abo`; the small source manifest is `evaluation/fixtures/abo-manifest.json`. Use a fresh output path for a repeat; the command refuses overwrite. A new overall finalization timestamp can differ, so deterministic comparisons use selected image/listing relationships, source provenance and splits. Existing downloads are reused only after size and hash verification. Redirects, unexpected HTTP status, path escapes and bodies exceeding their bounds are rejected. Missing length headers are accepted only when the stream ends below the remaining bound. `download-ledger.json` records completed objects; `transfer-bytes.json` also accounts for failed bodies, so restarting does not reset the acquisition allowance. Do not delete these ledgers to retry around a budget limit. Do not run concurrent acquisitions into the same root.

Each listing shard runs serially in a fresh child with `-I -S -X utf8 -X faulthandler`. The child retains only fields used by selection and records the source shard and line. Limits are 2 MiB per record, 128 MiB decoded per shard, 8 MiB projected output and 30 seconds per child. Nonzero exits, timeouts, malformed results and mismatched shard hashes fail finalization. Pydantic and Pillow load only after metadata parsing. The image index is streamed, retaining only IDs referenced by candidate listings. Selection preserves category order, hashed listing order, first marketplace record and main/alternate view rules. Original index paths, listing membership, decoded dimensions and byte hashes are checked before a manifest is written.

An acquisition or integrity error must be reported with the failing object/phase. A partial cache is not a completed evaluation set, and an absent manifest must not be replaced by fabricated image records. Metadata-only mode remains useful when a safe image acquisition cannot complete.

## Independent review

[product_data.py](../evaluation/product_data.py) validates the source manifest and local original bytes without network access. It also creates a separate review template:

```powershell
.venv\Scripts\python.exe evaluation\product_data.py review-template --manifest evaluation\fixtures\abo-manifest.json --output var\evaluation\abo\reviews.json
.venv\Scripts\python.exe evaluation\product_data.py check --manifest evaluation\fixtures\abo-manifest.json --root var\evaluation\abo --reviews var\evaluation\abo\reviews.json
```

The template refuses overwrite and records no human review by itself. Original manifest fields remain pending even when a separate review ledger is supplied. Review entries bind to the exact image ID and SHA-256 so changed bytes cannot inherit labels.

For each original image, an independent human reviewer should:

1. Inspect the pixels before reading model output. Record whether the image appears photographic, rendered, composite, or uncertain in `ambiguity_notes`.
2. Transcribe only readable markings. Record absent, small, blurred or obstructed labels and similar-looking connectors/components. Metadata titles, model numbers and product-page identity are not visual proof.
3. State separately whether a marking is visible, exact identity is visually established, and a revision is supported. Unsupported identity or revision remains false, with a reason; a revision claim needs a readable marking and an explicit supported revision label.
4. Record reviewer, timezone-aware review time, independent-human-review declaration and support notes. Mark an entry reviewed only after all three truth questions have explicit answers. Unfinished inspection stays pending.
5. Check that difficult cases are represented: missing identifiers, unreadable text, partial views and similar appearance. If metadata selection did not provide these cases, report that limitation before making recognition claims.

The ledger validator checks completeness and internal consistency; it cannot certify a person's independent judgment or the truth of a label. No automated script may set the human-review declaration on a reviewer's behalf. Machine suggestions can be stored separately, but cannot silently become human ground truth.

## Evaluation boundaries

All views of a listing share a deterministic development/holdout split based on its listing ID. The same item across marketplaces remains one group, and identical selected bytes cannot occur twice. A listing group is not a physical return ID; the collection does not claim separate physical units or real cross-return kit compatibility. Do not create product BOMs or revision mappings from listing text alone.

Pending or missing review entries contribute **zero images to an accuracy denominator**. Report total images, listing groups, pending/reviewed counts, split, failed/invalid model outputs, and unsupported claims separately. A valid JSON response is a protocol result, not a correct recognition. Model confidence wording is not a calibrated probability. Images cannot establish hidden function, electrical safety, internal damage or completeness outside the visible view.

Future model evaluation must preserve source hashes, ordered image references, model revision, prompt/schema versions, runtime settings and actual failures. Development changes use the development groups; do not tune against holdout labels and then report those same groups as independent validation. Results remain unverified evidence proposals in ReKit, with human verification, deterministic compatibility and transactional inventory authority unchanged.
