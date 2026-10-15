# Block C judge-workflow review

Review scope: the accepted Block B checkpoint
`609190e623c2561b067b871383fabfba1b1b2606`, its recorded canonical browser
workflow, and its actual local-NVIDIA evidence. This is an engineering and
presentation review by the project assistant, not independent human evaluation.
Mission 06 remains open; no AMD generation is authorized.

## Findings before changes

The canonical demonstration is explicitly synthetic and scripted. Three returns
provide four unique objects: two bodies in one return and one adapter in each of
two other returns. Nine original diagrams support the final histories. It tests
the existing authority and inventory workflow; it demonstrates neither physical
rebuilding nor real-world recognition accuracy.

| Judge question | Observed evidence | Remaining friction |
| --- | --- | --- |
| What entered? | Intake shows four held physical components and original synthetic diagrams. Original IDs and source returns persist into the plan and completed kits. | Intake is an operator form, not a summary of all three returns. The recording should establish the three-return/four-object map before showing the form. A second dashboard is unnecessary. |
| Why reject B? | `compatibility-denied.png` explicitly states adapter/B is not approved by `synthetic-standard-policy` version 1; allowed revisions: A. | The rejection is below the review form. The recording must hold this actual result in view; no new policy explanation is needed. |
| Why accept the later correction? | `canonical-correction-history.png` compares B at evidence v4 with A at v6, preserving both assertions and their links. The added original observation is at v5. | Shared earlier links and the newly cited close-up look identical. Gallery display order is not chronology. A precise newly-cited label would guide attention without asserting what the image proves. |
| Why rebuild? | `plan-overview.png` shows the server's optimal USD 175.00 result, two USD 87.50 actions, physical allocations, 60 labor minutes and zero solver gap. | Labor rate and capacity are inside raw scenario JSON; per-action arithmetic is written in cents. Showing existing snapshot assumptions and formatted arithmetic would make the result understandable without opening JSON. |
| Why liquidate at higher labor? | `canonical-high-labor.png` and `canonical-economics.json` preserve USD 85.00 liquidation at USD 2.00/minute; validated receipts compare USD 70.00 rebuild and USD 16.00 retention under that same rate. | The UI displays the selected proposal, not complete competing allocations. The deck should show the existing validated comparison table. The client must not invent alternative feasibility or become another optimizer. |
| Why does the second reservation fail? | `canonical-reservation-conflict.png` shows the actual already-reserved/consumed conflict and all four objects still reserved. The rejected proposal remains proposed. | Hold the error and reserved count together. Explain that a second proposal is allowed, while duplicate execution allocation is rejected. |
| Where did the kits come from? | Desktop/mobile final inventory shows two completed records. Each component links to evidence and names its source return; the recovery audit preserves approved snapshot versions. | The audit link is needed to distinguish current evidence from the approved snapshot. Existing wording already makes that distinction. |

All referenced before captures are in
[`run-canonical-k0p7d3pw`](../var/mission02-acceptance/run-canonical-k0p7d3pw/acceptance-result.json).
They are recorded application states, not mockups. Desktop layout is orderly;
mobile correction columns wrap, and the inventory table scrolls within its
container. The source and audit actions remain visible on mobile.

## Bounded implementation design

Record this design before application edits. Add a read-only summary of the
selected plan's immutable economic assumptions and currency-formatted selected
action arithmetic. Use existing scenario and returned action fields only;
preserve server-reported totals, and suppress a derived explanation if its
arithmetic or source association does not reconcile. No alternate feasibility,
new candidate generation, optimum, or independent economic result is computed
by the UI. Existing complete-alternative receipts remain the comparison source.

Label an observation as newly cited only when its ID is in the latest assertion
and absent from the explicitly superseded assertion. This describes citation
membership, not image age, relevance, correctness or independent verification.
Do not label when the superseded assertion is unavailable.

Affected modules: a focused plan-summary component and tests, the existing
recovery render integration, evidence-history rendering/tests, and minimal CSS.
No backend, API, authorization, schema, planner, dependency or environment change
is needed. Immutable input and association tests, relevant frontend tests,
TypeScript/build and canonical desktop/mobile browser checks must pass before
delivery. The original evidence and frozen review package remain untouched.

## Implemented changes and focused checks

The plan now exposes labor rate, total capacity, selected labor, component/return
counts and demand limits from the proposal's immutable snapshot. Selected actions
show currency-formatted gross, labor and other-cost arithmetic that reconciles
exactly to the recorded server cash result. Retention displays noncash donor
value separately. Missing/ambiguous associations, unsafe arithmetic or a mismatch
with recorded amounts suppress the additional calculation instead of overriding
the returned result. Held actions receive no invented cash explanation. No
alternative is asserted feasible by this display.

The correction comparison now marks the additional citation with **Newly cited
in this correction**. Prior/shared citations remain unchanged. The marker is
absent for a first assertion or when the superseded assertion is unavailable.
A test covers an older observation first cited in the later correction, ensuring
the label does not imply newly captured evidence. Existing original-image link
checks and immutable history remain intact.

Focused validation used `npm.cmd test -- --run src/plan-summary.test.tsx
src/evidence-history.test.tsx src/App.test.tsx`: **46 tests passed in 29.22 s**.
`npm.cmd run typecheck` passed. Tests cover the actual canonical baseline and
higher-labor fixture amounts, retention, salvage, negative cash, unknown limits,
missing selection, conflicting amounts, duplicate/missing source associations,
unsafe arithmetic, unchanged input objects and correction citations. An initial
type-check failure identified that the test's source JSON omits the existing
backend default `salvage_labor_minutes`; the UI test now explicitly supplies
that zero default. Production contracts were not changed to accommodate a test.

The changed display contains no new request, form, authority or external URL.
React text rendering preserves existing escaping, and no original evidence,
credential, frozen package or model configuration was modified by these changes.
Full-suite, browser and visual after-checks are recorded in the Block C delivery
report; focused checks alone do not establish those results.

## Browser after-check and visual comparison

The root agent's actual canonical browser replay passed in **8.3 seconds** with
Chrome `155.0.8059.41`. The [acceptance receipt](../var/mission02-acceptance/run-canonical-jheftnar/acceptance-result.json)
records 24 captures, zero page errors, no document overflow at 1440/390/320-pixel
viewports, nine original managed images, the unchanged USD 175.00 baseline and
USD 85.00 sensitivity, rejected competing approval (409), two completed kit
records and four consumed components. New browser assertions check the visible
assumptions, selected-action calculations and newly cited observation label.
The [runner receipt](../var/mission02-acceptance/run-canonical-jheftnar/runner-result.json)
confirms no inference, successful disposable-state/credential cleanup and empty
cleanup/reporting errors.

Eleven resulting captures were visually inspected for this judge review:
the four focused assumptions/calculation captures, desktop/mobile correction,
desktop/mobile final inventory, plan overview, reservation conflict and completed
source lineage. The changes show no clipping or overlapping text in those
captures, and no further application redesign is justified by this inspection.

| Improvement / preserved behavior | Before | After / visible result |
| --- | --- | --- |
| Baseline assumptions and dollar arithmetic | [Plan overview](../var/mission02-acceptance/run-canonical-k0p7d3pw/plan-overview.png): labor rate buried in JSON, arithmetic in cents. | [Focused desktop](../var/mission02-acceptance/run-canonical-jheftnar/canonical-assumptions-desktop.png): USD 0.25/minute, 60-minute capacity/selection, four components/three returns and USD 100.00 − 7.50 − 5.00 = 87.50 per selected rebuild in one view. |
| Higher-labor explanation | [Higher-labor plan](../var/mission02-acceptance/run-canonical-k0p7d3pw/canonical-high-labor.png): selected liquidation is visible, but assumption detail needs expansion. | [Focused sensitivity](../var/mission02-acceptance/run-canonical-jheftnar/canonical-high-labor-assumptions.png): USD 2.00/minute, 10 selected minutes, unchanged capacity/pool and selected liquidation calculations. |
| Narrow-screen economics | The older plan relies on the raw snapshot for its rate. | [Mobile assumptions](../var/mission02-acceptance/run-canonical-jheftnar/canonical-assumptions-mobile.png) and [mobile calculation](../var/mission02-acceptance/run-canonical-jheftnar/canonical-calculation-mobile.png) wrap naturally while keeping currency, assumptions and source IDs readable. |
| Citation difference | [Correction comparison](../var/mission02-acceptance/run-canonical-k0p7d3pw/canonical-correction-history.png): all evidence links look alike. | [Current comparison](../var/mission02-acceptance/run-canonical-jheftnar/canonical-correction-history.png): the evidence-v5 citation is visibly marked, while v2/v3 citations remain shared. [Mobile comparison](../var/mission02-acceptance/run-canonical-jheftnar/canonical-correction-mobile.png) shows the upper comparison columns wrapping correctly; the citation row is below that captured viewport. |
| Exclusive allocation and final lineage | Existing safeguards and source navigation were already shown in Block B. | [Conflict](../var/mission02-acceptance/run-canonical-jheftnar/canonical-reservation-conflict.png), [desktop kits](../var/mission02-acceptance/run-canonical-jheftnar/final-inventory.png), [mobile kits](../var/mission02-acceptance/run-canonical-jheftnar/final-inventory-mobile.png) and [original-source navigation](../var/mission02-acceptance/run-canonical-jheftnar/canonical-completed-source-lineage.png) preserve those behaviors with the new display. |

Use focused views for recording/deck details, with a preceding context view.
The full plan capture is now 2,936 pixels tall; the complete source-history
capture is 4,817 pixels tall. Scaling either entire image into a single slide
would make supporting text too small. Actual scrolling or clearly identified
detail crops communicate the evidence better. Gallery order remains incidental:
identify the close-up by its original association/hash and evidence-v5 history,
not a permanently assigned image number.

## Competitive assessment

ReKit's strongest supported contribution is the connected path from uncertain
visual evidence through explicit human authority and deterministic compatibility
to economic allocation, exclusive reservations and auditable completion. Lead
with that connection, rather than a claim that image recognition alone is new.
The existing implementation and receipts support it; no market-first or
competitor-superiority claim is established.

The economics are credible as transparent scenario calculations with a controlled
counterfactual, not measured business impact. Show the USD 0.25/minute and USD
2.00/minute rates, 60-minute capacity, two-kit demand and invented estimates next
to the comparison. Retained value is noncash. The selected baseline exceeds
complete liquidation by USD 72.50; the higher-labor result changes because two
rebuilds consume 60 minutes while complete liquidation consumes 10.

Keep failures visible: B compatibility rejection, new-evidence hold, reservation
conflict, and the local model's repeated text/incomplete uncertainty/unnecessary
view request. The product-image inspection is local NVIDIA on original ABO
catalog views used as simulated intake; it supplies no verified parts to the
synthetic kits. Independent review remains pending, and zero successful AMD
visual inference is still the deployment blocker. Tests establish implementation
behavior, not model accuracy, physical safety or real recovery savings.

High-value next actions are the actual human review, a concise recording of this
single story, owner review of the candidate deck, and a resolved AMD API contract
followed by separately approved qualification. New feature screens or unsupported
market claims would not address the demonstrated gaps.
