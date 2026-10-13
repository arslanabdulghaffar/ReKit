# Real product image evaluation

Mission 04 uses a small Amazon Berkeley Objects (ABO) catalog-image collection to move beyond synthetic illustrations. Acquisition and file integrity do not establish recognition accuracy. The source manifest keeps every visual-truth field unknown and every image pending until a separate human review is recorded. Catalog images also require review for photographic, rendered, or composite content; they are not automatically evidence of returned physical components.

**Task 1 is accepted and verified at commit `5506b69bb827ef2b4c836d0adac8c1577b10a997`.** The separately authorized recovery reused 21 metadata objects (93,897,585 bytes) and 52 original image objects (9,809,702 bytes), without downloading them again. `evaluation/fixtures/abo-manifest.json` now records 52 images in 48 listing groups, including four additional same-listing views. Image splits are 34 development and 18 holdout. Source categories contain 12 power-accessory images and eight in each of the other five categories. Human-reviewed labels remain **0**; no recognition accuracy is claimed.

Contact-sheet triage found a logo-only image (`61OnkGVhMWL`), USB reference charts (`51ajqjMk6hL` and `51a0DlkplcL`), and composite imagery. This is a collection of 52 catalog images, **not 52 verified product photographs**. That observation does not complete independent ground-truth review; all 52 entries remain pending. Later inference must report this source-content limitation and identify any subset used for product-view examples.

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

## Task 2 baseline method

[run_product_evaluation.py](../evaluation/run_product_evaluation.py) selects cases before examining model output. In manifest order, it takes two development images from distinct listing groups in each of the six categories, followed by one same-listing two-image development case. The current manifest has only one eligible development pair: `71rr7OjqWqL` and `812Xgtrv0EL`, listing `B07XGQ9QJF`. Their order is preserved. The sample therefore contains **13 requests, 14 image presentations, 13 unique images and 12 listing groups**. The joint case reuses one single-case image; the requests are not 13 independent products. No holdout image is used.

The runner verifies the source manifest and all original image bytes before constructing the lazy provider. It then calls one `LocalVisionProvider` sequentially, rechecking selected input bytes before each call. No database, API endpoint, component identity or inventory record is created. The full configuration, manifest hash, ordered input hashes and case plan are saved before inference. Actual execution results, including raw Unicode model text, are saved before provenance validation and strict parsing. Output files must be new JSON files under ignored `var` storage; each completed artifact write is replaced atomically. There are no hidden model retries. An unavailable provider leaves remaining cases explicitly unattempted; individual parsing/runtime failures remain in the report.

The recorded historical baseline used `Qwen/Qwen3-VL-2B-Instruct`, revision `89644892e4d85e24eaac8bacfd4f463576704203`, the existing `rekit-inspection-v5-constrained` prompt and the `rekit-inspection-schema-v1` decoding schema. **No approved catalog is supplied.** The prompt instructs the model to return no identity candidates. In addition, the decoding schema requires at least one uncertainty string. Empty candidates and uncertainty are therefore instructed/constrained behaviors, not evidence that the model independently recognized an unknown product. Natural-language observations can still contain unsupported identity, marking or capability claims and require review. The current implementation uses schema v2's additional catalog-scope restriction described below; running it does not reproduce the historical v1 behavior.

The existing preprocessing applies EXIF orientation, RGB conversion and a maximum image side of 768 pixels before the official processor, whose configured image area bounds are 65,536–589,824 pixels. These transforms can remove small label detail even when the original is readable. The input limit is 8192 tokens; generation is greedy, capped at 512 new tokens, with a cooperative 120-second adapter deadline. The review queue displays original source images; it does not imply that the model received their full original resolution. No new crop, OCR model, inference model, package upgrade or prompt improvement is part of this baseline.

To run the current implementation with the existing model installation, choose a fresh output filename:

```powershell
.venv\Scripts\python.exe evaluation\run_product_evaluation.py --output var\evaluation\abo\qwen-current-new.json
```

Optional `--manifest`, `--root`, `--model-dir` and `--device` arguments select already available local inputs; CUDA device 1 is the default. The command does not download missing models or images. A completed run with invalid responses returns a nonzero exit code while preserving all observed outputs and errors. The original v1 record is preserved at `var/evaluation/abo/qwen-baseline-v1.json`. Re-executing that historical baseline requires the Task 1 provider/schema code plus the original evaluation runner; the command above uses current code instead. The saved baseline records the actual original configuration, prompt/schema hashes, inputs and raw responses, and is the comparison source.

## Recorded baseline and targeted catalog-scope correction

The baseline finished all **13 requests** on `cuda:1`. Its then-current schema and provenance checks accepted 13/13 responses, but **9/13 responses emitted candidates despite the no-catalog instruction**. Each of those nine candidates also carried a revision and quoted marking. Only 4/13 responses abstained with empty candidates. These are directly countable protocol behaviors, not independently reviewed visual error rates. All semantic accuracy fields remain null with zero reviewed cases.

| Measured result | Original schema v1 | Catalog-scope schema v2 |
| --- | --- | --- |
| Attempted / completed requests | 13 / 13 | 13 / 13 |
| Accepted schema/provenance responses | 13/13 | 13/13 |
| Responses with candidates despite no catalog | 9/13 | 0/13 |
| Instructed abstention | 4/13 | 13/13 |
| Observations / marking observations | 23 / 5 | 23 / 5 |
| Identity candidates / revision candidates | 9 / 9 | 0 / 0 |
| Revision-marking quotes | 9 | 0 |
| Additional-view requests | 13 | 13 |
| Source-reference records / individual links | 45 / 45 | 36 / 36 |
| Inference latency, n=13: min / median / p95 / max | 33.314 / 50.594 / 90.833 / 90.833 s | 15.599 / 20.942 / 35.416 / 35.416 s |
| Wall latency, n=13: min / median / p95 / max | 33.404 / 50.717 / 90.998 / 90.998 s | 15.658 / 21.022 / 35.513 / 35.513 s |
| Cold inference, n=1 / warm median, n=12 | 55.105 / 50.519 s | 24.763 / 20.269 s |
| Model load time, one cold load | 4.694 s | 3.879 s |
| Model-load peak allocated bytes | 4,256,128,000 | 4,256,128,000 |
| Inference peak allocated bytes, n=13 | 4,904,651,776 | 4,904,651,776 |
| Inference peak reserved bytes, n=13 | 4,980,736,000 | 4,980,736,000 |
| Independently reviewed semantic cases | 0 | 0 |

This observation justified one narrow correction: when `LocalVisionProvider` receives no catalog, schema v2 forbids identity candidates and records `generation.identity_candidates_allowed=false`. Catalog-backed requests retain their unverified candidate channel. The API service and evaluator pass that admitted permission into strict parsing; a forbidden candidate makes the complete response invalid, preserves its raw text, and produces no evidence events. The implementation never deletes a candidate from the model's response to make it appear valid.

The first decoder test exposed a concrete limitation in pinned LM Format Enforcer 0.11.3: `maxItems: 0` alone still allows the first array member. Two actual character-parser tests failed while 90 other focused tests passed. The installed package was not modified. A local immutable `CharacterLevelParser` guard now permits only an empty top-level `candidates` array when the admitted schema disallows candidates, while retaining the library's schema checks for other fields. It preserves its state across parser branches and handles whitespace, reordered fields and escaped string content. The strict parser remains a second check. The final four-file focused gate passed 146 tests, including the real decoder, provider configuration, runner propagation and HTTP no-events boundary.

Both runs finished successfully with the **same case plan and ordered original bytes**. Comparing the saved configurations confirms that model/processor revision, runtime versions, device, prompt version and SHA-256, preprocessing, token cap, sampling, deadline, dtype and attention are unchanged. The only configuration differences are the decoding-schema version, its one/two-image hashes, and the added `identity_candidates_allowed=false` flag. Both records use manifest SHA-256 `4c04cbf85ba9fe0d025b2f1dfd0c0d3c6dbd22a67f82daeb506f9c7b925758bc` and prompt SHA-256 `3fdef4495d4eba03cc6af53e9b1778afc7821d46d6d22460e0422bb5a9846fe2`.

The preserved artifact byte hashes are:

| Artifact under ignored `var/evaluation/abo` | SHA-256 |
| --- | --- |
| `qwen-baseline-v1.json` | `f731569d02617dd077843516a3a44d76c609c46ccf56908bf4c186a8a54aa128` |
| `qwen-after-v2.json` | `791dac0795263fc5e42978baf93cd568be177c484fd9b48111cc592a032730ea` |

Task 2 therefore made **26 actual local GPU requests and 28 image presentations**, reusing 13 unique images from 12 listing groups. No failures or cases were removed from either run. The measured change from 9/13 to 0/13 no-catalog candidate violations establishes enforcement of the supplied-catalog boundary. It does **not** establish better product recognition, correct free-text observations, accurate markings, useful additional views or safety judgment. All semantic metric denominators remain zero, and their rates remain null. No additional model, OCR package or crop transformation was introduced.

Latency was lower in the second execution, while the recorded peak allocated/reserved memory was unchanged. These are observations from one sequential pass per version, with different generated responses. This was not a repeated controlled performance benchmark, so the timing difference does not establish a causal speedup or a production latency guarantee. The tables round seconds to three decimal places; the artifacts retain the full recorded measurements. Model-load peak values appear in each request's metadata but represent one cold load per process, not 13 independent loads.

Validation for this Task 2 change passed 185 focused tests in 10.90 seconds and 806 backend tests in 36.58 seconds. The local browser review check displayed 13 case cards and 14 images at desktop/mobile sizes and exported an assessment containing zero reviewed cases. Package consistency passed, and the scoped secret check covered 125 files without findings. Those checks establish software behavior and review availability; they do not supply human labels or semantic accuracy.

## Output assessment workflow

[product_review.py](../evaluation/product_review.py) creates a local HTML queue and a separate output-assessment file from a **finished** evaluation record:

```powershell
.venv\Scripts\python.exe evaluation\product_review.py create --manifest evaluation\fixtures\abo-manifest.json --root var\evaluation\abo --result var\evaluation\abo\qwen-baseline-v1.json --output-dir var\evaluation\abo\review-baseline-v1
.venv\Scripts\python.exe evaluation\product_review.py check --result var\evaluation\abo\qwen-baseline-v1.json --assessments var\evaluation\abo\review-baseline-v1\case-assessments.json
```

Open `var/evaluation/abo/review-baseline-v1/index.html` locally. The destination must be new; queue creation verifies original images and their manifest/result bindings. Each case displays inputs in the order supplied to the model, with source hashes and a collapsed provenance section. Model output is initially collapsed. Source and model strings are HTML-escaped, and the page cannot contact remote services or mutate inventory.

The completed schema-v2 run also has a queue at `var/evaluation/abo/review-after-v2/index.html`. Its assessment check reports zero reviewed and 13 pending cases. Use `qwen-after-v2.json` and that queue's own assessment file when checking those results; baseline and after-run assessments are not interchangeable.

There are two independent review records:

- The `product_data.py` image-review ledger describes what a human can establish from the original pixels. Complete it before reading predictions to limit anchoring on model guesses.
- `case-assessments.json` judges the particular model response, including prose outside `candidates`. It binds the full result digest, raw-output hash and ordered input hashes. Changing the execution record or image order invalidates the assessment. This does not modify the original image labels or the saved model output.

Every output judgment starts pending. A human reviewer supplies their name, review time, independent-review declaration and supporting notes. For identity, revision, marking and source attribution, choose unsupported if any relevant claim in that case lacks support, supported only if the relevant claims are supported, not present when no such claim exists, or undetermined when review cannot establish a judgment. For additional views, supported means useful and unsupported means unhelpful; explain what missing evidence the requested view would resolve. Marking comparison fields require a human transcription and the corresponding model text. Corrections are recorded as review text; they do not execute corrections in production inventory.

The HTML page downloads the edited assessment JSON when the reviewer explicitly exports it. Use the path of that downloaded file in `product_review.py check`; the untouched template remains pending. Neither the runner nor an assistant may mark a case independently human-reviewed on the reviewer's behalf.

## Metric definitions and exclusions

| Metric | Numerator and denominator or measured population |
| --- | --- |
| Accepted schema response rate | Strictly parsed responses with matching provider, model, device, ordered image hashes, visual encoder execution and decoding-schema provenance / attempted requests. Runtime and parsing failures remain in the denominator. |
| Instructed abstention | Valid responses with no candidates and explicit uncertainty / valid responses. This is not identity-recognition accuracy. |
| Output counts | Validated observation, candidate, revision, marking, image-reference and additional-view records. These are occurrence counts, not supported-claim judgments. |
| Unsupported identity/revision/marking | Independently assessed cases judged unsupported / cases judged supported or unsupported for that field. These are case-level rates, not individual-claim rates. |
| Incorrect image attribution | Cases judged unsupported for source attribution / cases with a supported-or-unsupported source judgment. Valid index numbers alone do not establish visual attribution. |
| Useful additional views | Cases judged useful / cases with useful-or-unhelpful judgments. Absent requests are excluded. |
| Transcription exact match | Reviewed pairs of human/model strings that are exactly equal / reviewed transcription pairs. No case, whitespace or spelling normalization is applied; this is not a character-error-rate measure. |
| Human corrections | Independently reviewed cases containing a nonblank correction / independently reviewed cases. |
| Latency | Actual per-attempt wall time and measured inference time; inference is also separated into first-load and warm requests. Report sample count, minimum, median, nearest-rank p95 and maximum. |
| GPU memory | Actual recorded load/inference peak allocated and peak reserved bytes, with measurement count and maximum. Missing measurements are excluded, never replaced with zero. |

Not-present, undetermined, pending and missing human assessments are excluded from each semantic metric's denominator. The checker reports each exclusion count. A zero eligible denominator produces a null numerator/rate, never a claim of 0% error. The runner's semantic fields remain unmeasured; the separate assessment checker supplies review-based rates only when genuine reviews are available. Failed responses that retained raw text can still be assessed for harmful or unsupported claims.

Cold request wall time includes model initialization; adapter `inference_seconds` measures processing/generation after model loading. Wall time also includes input reading and the runner's pre-execution bookkeeping. With this small sample, p95 may equal the maximum. Report image presentations and listing groups alongside request counts, and preserve the photographic/composite/reference-image limitation in every quality summary.
