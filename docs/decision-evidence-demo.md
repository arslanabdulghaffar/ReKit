# Block E recorded decision-evidence demonstration

This standalone, offline artifact explains how evidence, permission to use a
physical component, and the best economic allocation differ. It reads six
**saved synthetic Block D scenarios**. It does not run inference or optimization,
verify an identity, approve compatibility, reserve inventory, or change ReKit.
It is separate from both the production workbench and independent human review.

## Open and review

From PowerShell at `A:\hackathon\ReKit`, authenticate the selected package first:

```powershell
.\.venv\Scripts\python.exe -B evaluation/build_decision_evidence_demo.py --check var/mission06-offline/block-e-decision-demo-20261015-234317-740907
if ($LASTEXITCODE -ne 0) { throw 'Package verification failed; do not use this copy.' }
Start-Process 'A:\hackathon\ReKit\var\mission06-offline\block-e-decision-demo-20261015-234317-740907\index.html'
```

Alternatively, after checking, open the [selected comparison](../var/mission06-offline/block-e-decision-demo-20261015-234317-740907/index.html)
in Chrome or Edge. No server, installation or sign-in is needed. Opening HTML
alone does not authenticate its bytes; the command above does.

1. Read the synthetic scenario and its three returns/four physical IDs.
2. Choose **$0.25 / minute**. Compare compatibility, permission, allocation and
   the cash/noncash breakdown across historical B, review required and corrected A.
3. Choose **$2.00 / minute**. B and A both favor all-return liquidation; the held
   state still excludes adapter 002. An unchanged economic choice never waives review.
4. Expand each **Recorded solve and physical allocation** to see actual action
   IDs, source component IDs, input fingerprint and saved optimality result.
5. Expand **Compare the original synthetic views**. Open the full-resolution
   originals: the first two are unclear, while the added close-up shows A. The
   B assertion and later human correction were scripted; they are not real reviews.
6. Optionally open the [three-point labor visual](../var/mission06-offline/block-e-decision-demo-20261015-234317-740907/sensitivity.html).
   Return to the main comparison afterward. Both pages expose their full receipts
   and source/schema copies under **Inspect the saved evidence and integrity checks**.

Tab reaches the labor buttons; Enter or Space activates them. They only select
recorded scenarios. The comparison controls remain visible while scrolling.
There is no save, export of judgments, operational action or editable identity.
Use the separate [human-review guide](independent-review-guide.md) for actual assessments.

## Recorded results

All values below are modeled USD totals under invented assumptions. Retained
donor value is noncash; the artifact shows it separately.

| Saved state | At $0.25/minute | At $2.00/minute |
| --- | --- | --- |
| Historical scripted B, version 4 | $107.75: one rebuild, liquidate adapter 002, retain one body; $101.75 cash + $6 retained | $85: liquidate all three returns |
| New close-up, review required, version 5 | $93.50: one rebuild, retain one body, hold adapter 002; $87.50 cash + $6 retained | $76: liquidate two returns, hold adapter 002 |
| Scripted corrected A, version 6 | $175: two rebuilds | $85: liquidate all three returns |

The held snapshot preserves the old B assertion as history, without a fresh
verified identity. It does not permit consuming adapter 002 through rebuilding,
liquidation, salvage or eligible donor retention. Correction changes the permitted
rebuild set; the optimizer still compares complete feasible allocations.

The optional supplement shows actual saved corrected-A runs:

| Labor/minute | Two rebuilds | All-return liquidation | Global optimum in tested domain |
| --- | --- | --- | --- |
| $1.69 | $88.60 | $88.10 | Two equal-value physical rebuild pairings |
| $1.70 | $88.00 | $88.00 | Three ties: both rebuild pairings and liquidation |
| $1.71 | $87.40 | $87.90 | One liquidation allocation |

The underlying study checks all **210 feasible complete allocations** at all
**201 integer-cent labor rates** from $0.00 through $2.00/minute. This is stronger
than comparing two selected lines, but it shares candidate generation and
assumptions with the planner. It is not independent validation of business inputs,
real revenue, a market threshold, probabilities, expected value of information,
or advice about future image capture. It establishes no hidden functional or
safety property. AMD execution remains pending.

## Integrity and reproduction

The selected package contains 16 files: two HTML pages, three byte-identical
original diagrams, full source receipts, schema/source/fixture copies, compact
presentation data, README, build checks and manifest. Manifest SHA-256:
`2f13b7d80017f4078794f052dfc610a2ebe30ef8a3d7aa87e4bf4c56fc717f27`.
Its source receipt is the preserved
`var/mission06-offline/block-d-canonical-sensitivity-20261015-224735/receipt.json`,
SHA-256 `cb565d5cdf87a46aa68bc02f3fe4b34da619c9d45d54c8304c63faf787a4ee3f`.

The [builder](../evaluation/build_decision_evidence_demo.py) authenticates frozen
source hashes, strictly validates all 207 saved plans, checks input fingerprints,
all complete allocations and ties, and regenerates expected presentation bytes.
`--check` rejects changed, missing or unexpected files. Build and check perform
no new solves. New outputs must be unused directories under ignored
`var/mission06-offline`, without symlinks or Windows junctions in the path.
The package contains synthetic nonsecret evidence and inherits filesystem ACLs;
it is not an access-controlled public service.

To create another candidate, choose a genuinely unused suffix:

```powershell
.\.venv\Scripts\python.exe -B evaluation/build_decision_evidence_demo.py --output var/mission06-offline/block-e-decision-demo-owner-review-01
```

The [browser acceptance helper](../evaluation/check_decision_evidence_demo.mjs)
checks a verified package using installed Chrome/Edge and existing Playwright:

```powershell
node evaluation/check_decision_evidence_demo.mjs var/mission06-offline/block-e-decision-demo-20261015-234317-740907 var/mission06-offline/block-e-decision-qa-owner-01
```

Use a new QA directory. The final development run is retained at
`var/mission06-offline/block-e-decision-qa-reviewed/`: 18 screenshots, six-state
values, original-image loading, keyboard controls and 1440/390/320px layouts
passed, with no page errors or forbidden requests and unchanged package bytes.
Storage-method hooks observed no mutations; the broader no-storage conclusion
also relies on source review, not comprehensive browser-storage instrumentation.

## Presentation assessment

Agent visual and code review found this useful as an optional explanation of a
specific distinction: better identity evidence can alter compatibility without
altering the economic winner, while unresolved evidence still blocks use. The
three-point supplement answers a deeper question about the labor threshold and
ties. Six states and three close rates add cognitive load to a four-minute pitch;
keep them available for Q&A rather than enlarging the main seven-slide story.

This is a reasoned presentation assessment, not measured human usability or
independent reviewer evidence. Owner review remains pending. Neither page was
inserted into the approved Block D deck or production application. Any later
integration needs a separate review of usefulness, semantics and operational
authority; the artifact itself supplies none.
