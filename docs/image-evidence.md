# Managed image evidence

The configured API accepts JPEG, PNG, and WebP photographs through
`POST /components/{component_id}/images?return_id={source_return_id}`. Send the raw
file body with its exact image media type and an intake-role bearer credential.
No multipart parser, client filename, storage path, or client asset ID is used.
Extra query parameters are rejected. Reads require the viewer role:

- `GET /components/{component_id}/images`: asset metadata and current availability.
- `GET /assets/{asset_id}`: one asset's metadata and current availability.
- `GET /assets/{asset_id}/content`: authorized, integrity-checked image bytes.

## Bounds and validation

The API limits both declared length and streamed bytes to 10 MiB (10,485,760
bytes). The storage layer independently checks that limit. Images may contain
at most 16,000,000 pixels and each dimension may be at most 8,192 pixels.
Animated/multiple-frame files are rejected. The declared media type must match
the decoded format. Decoding is restricted to the supported formats and checks
dimensions before pixel loading, verifies the file, then reopens and loads it.
Neither a filename extension nor an EXIF claim establishes validity.

The implementation uses the already-installed, pinned Pillow 12.3.0. Pillow
opens lazily, so explicit verification and pixel loading are needed in addition
to opening the file; decompression warnings/errors are treated as rejection.
See the [Pillow Image API](https://pillow.readthedocs.io/en/stable/reference/Image.html).

## Identity and provenance

Each accepted asset has a server-generated immutable ID, SHA-256 of the original
bytes, byte size, decoded dimensions, media type, authenticated uploader,
server receipt time, component ID, return ID, and generated observation ID.
The image is attached to an existing physical component and its registered
source return; an upload never registers another physical item.

The generated observation uses `asset:{asset_id}` and the server receipt time.
That timestamp records admission, **not** a verified camera shutter time. EXIF,
the apparent subject, and the scene's authenticity are not trusted capture
facts. Human uploads are operator-source observations; service uploads are
import-source observations. Both remain unverified evidence.

Distinct views create distinct observations of the same item. Repeating the
same bytes for the same item returns the original asset/observation with
`duplicate: true` (HTTP 200 rather than 201), preserving the original uploader
and receipt time. Reuse under another physical ID is rejected with 409 for
review. A hash proves byte identity, never physical-object identity. Recaptures,
cropping, and re-encoding can defeat byte-level duplicate detection.

## Storage and integrity

`REKIT_EVIDENCE_DIR` selects a trusted local directory; without it the configured
factory uses `evidence` beside the database. The example uses ignored
`var/evidence`. Asset metadata and generated observations share the existing
SQLite database and one write transaction. Metadata and evidence references
are append-only. File names are server-assigned and path containment is checked.

The complete original file is exclusively created and flushed before committing
its metadata and observation. A handled failure rolls back database changes
and removes only the file just created by that operation. SQLite and the file
system are not a single atomic storage engine: a process or machine crash can
leave an unreferenced orphan file. No automatic orphan deletion is implemented.
Back up and restore the database and evidence directory together.

Retrieval reads bounded bytes and verifies length and SHA-256 before returning
the exact checked bytes. It never exposes a public static folder or accepts a
credential in a URL. Responses prohibit caching and content sniffing. Metadata
reports `available`, `missing`, `corrupt`, or `unavailable`. Unknown IDs return
404; known missing files return 410; integrity conflicts return 409; filesystem
failures return 503 without a local path in the response. Invalid uploads use
413 (limits), 415 (format/type), or 422 (corrupt/invalid bytes).

## Recovery authority and limits

Uploading does not infer identity, visible condition, compatibility, or eligibility.
A new view after verification returns the component to review through the existing
evidence rules. After reservation, a new view also invalidates the approved
evidence snapshot; cancel, review, and replan before physical work. Once a plan
is partly completed, supervised recovery is not yet implemented, so intake is
not a completion-photo workflow. HTTP verification checks managed references it cites; approval
and completion check the managed references used by current verification.
Completion images must belong to a component in that action. These checks fail
closed when storage is absent or required managed evidence is missing/corrupt.
An unrelated unused historical photo does not invalidate a later verification.
An exact retry of an already-recorded, actor-bound assertion or execution command
returns the current state without making another decision, even if an asset has
since become unavailable. The transactional command rechecks the immutable
operation record. Changed actors or payloads still conflict; new decisions still
require valid managed evidence. Re-uploading bytes never repairs a missing asset.

Legacy text references remain explicitly unmanaged: they are not fetched, decoded,
or presented as authenticated assets. Internal Python stores are trusted application
calls. Local administrators can change files or databases; hash checks detect
file changes but are not cryptographic attestation against an administrator.
The integrity checks assume the application is the only file writer; they do not
provide cross-resource locking against hostile local filesystem changes.
There are no malware scanning, retention deletion, quotas, or rate limits yet.
Keep the service on loopback. An image cannot establish hidden functionality
or safety, and no vision model runs during intake.
