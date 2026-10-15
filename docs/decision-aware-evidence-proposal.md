# Decision-aware evidence: bounded proposal for owner review

ReKit could make an additional-view request more useful by explaining **which unresolved fact could change a recovery decision under the current assumptions**. The narrow opportunity is a read-only conditional comparison: “If a human verifies revision A, this plan becomes feasible; if B is confirmed, this is the best permitted alternative.” This can explain the reason for inspecting a marking without predicting what the photograph will show.

Recommend a small, offline demonstration card only after owner approval. Start with the saved synthetic adapter correction and its six already measured conditional results. No runtime, UI or new capture-ranking feature has been implemented. A live operator feature would need a separate scope review because hypothetical identities must never become verified inventory.

## What the evidence supports

The [Block D sensitivity receipt](../var/mission06-offline/block-d-canonical-sensitivity-20261015-224735/receipt.json) compares three saved states of `synthetic-adapter-002` at the existing low and high labor assumptions. The historical B assertion was deliberately wrong in the scripted case. The held state is the actual saved `review_required` state after another original image was added; its old B assertion remains in history. Corrected A is the subsequent scripted human assertion. These are conditional planning snapshots, not independent human judgments or predictions of an unseen product.

| Labor rate | Saved evidence branch | Globally optimal action pattern | Estimated cash, USD | Retained noncash value, USD | Modeled total, USD |
| --- | --- | --- | ---: | ---: | ---: |
| 0.25/min | Historical scripted B | One rebuild; liquidate adapter 002; retain one body | 101.75 | 6.00 | 107.75 |
| 0.25/min | Review required; adapter 002 held | One rebuild; retain one body; hold adapter 002 | 87.50 | 6.00 | 93.50 |
| 0.25/min | Corrected scripted A | Two rebuilds | 175.00 | 0.00 | 175.00 |
| 2.00/min | Historical scripted B | Liquidate all three returns | 85.00 | 0.00 | 85.00 |
| 2.00/min | Review required; adapter 002 held | Liquidate the other two returns; hold adapter 002 | 76.00 | 0.00 | 76.00 |
| 2.00/min | Corrected scripted A | Liquidate all three returns | 85.00 | 0.00 | 85.00 |

All six runs used existing CP-SAT 9.15.6755 and returned OPTIMAL, with matching bounds and zero gaps. The allocation oracle checked 184 complete covers for B, 46 for held and 210 for A. It is independent of CP-SAT but shares the candidate generator and source assumptions; it does not validate business truth. Only the subject's evidence/eligibility and the stated labor rate changed; every other input stayed identical. Each result retains the full problem fingerprint and source JSON pointer under `/correction/before/current`, `/correction/before_correction/current` or `/correction/after/current`.

At low labor, a valid A correction changes the global action pattern from one kit plus other dispositions to two kits. At high labor, A still changes rebuild compatibility, but B and A both lead to the same optimal liquidation. This is a useful distinction a generic “take another photo” message cannot explain on its own. **The unchanged economic decision never waives required evidence or human review**: the held row still excludes adapter 002 from consuming dispositions, and restoring any authority requires the actual verification workflow.

The modeled difference is not the expected value of information. No probability of A versus B, chance of a readable photograph, capture cost, sale probability, risk utility or calibrated model confidence is available. The table therefore cannot justify “this photo is worth USD 67.25,” a capture priority score, a promised increase in revenue or an instruction to skip inspection. Its defensible claim is conditional: the approved facts can affect feasibility and the preferred modeled allocation.

## Existing boundaries that support the idea

| Existing implementation | What it provides | What it does not authorize |
| --- | --- | --- |
| [Inference contracts](../backend/src/rekit/inference/models.py), `AdditionalView` | A view description, reason and source-image indices; strict output structure | A link to a specific optimization constraint, calibrated outcome probability or verified identity |
| [Compatibility policy](../backend/src/rekit/catalog/compatibility.py), `check_compatibility` | Deterministic revision and visible-condition reasons for an approved configuration | Approval of a physical item merely because a hypothetical identity is compatible |
| [Evidence state and verification](../backend/src/rekit/evidence/store.py) | Append-only history; new observations require fresh review; verification cites observations and explicitly supersedes the prior assertion at an expected version | Replacing evidence or turning an LLM suggestion into human authority |
| [Recovery planner](../backend/src/rekit/recovery/planner.py) | Fingerprinted catalog, evidence, policy and economics; explicit complete candidates; CP-SAT statuses, bounds and alternatives | Business truth, hidden functional/safety properties or a probability distribution over outcomes |
| [Inventory transactions](../backend/src/rekit/inventory/store.py) | Approval rechecks policy, evidence, membership and conflicts before atomic reservations | Approval or execution of an unstored hypothetical branch |

The new offline [sensitivity runner](../evaluation/run_canonical_sensitivity.py) already demonstrates read-only copies of these saved evidence states without store writes or new assertions. This is research support for the proposal, not an implemented decision-aware capture service. Existing `AdditionalView` requests remain model observations; no new model or inference call is needed for this bounded example.

## Proposed first increment

Present one compact card next to a clearly labeled synthetic demonstration, titled “What would resolving this revision change?” Show the specific component, its original close-up, the approved rule that distinguishes A from B, and the three conditional rows. Let the reviewer switch only between the two existing labor assumptions. Label historical B, held and corrected A explicitly, and show cash and noncash values separately. Keep a visible source-receipt link and solver proof details.

Use only the existing frozen receipt and previously calculated results for this first increment. No arbitrary hypothetical input editor, automatic capture ranking, new optimizer, model calls, additional inference stack, live evidence mutation or production database access is needed. Do not put an “approve,” “apply identity” or “reserve” control on the card. Its role is explanation; actual intake, review, correction, planning and approval remain the working application's separate actions.

Bind the card to the exact receipt SHA-256 `cb565d5cdf87a46aa68bc02f3fe4b34da619c9d45d54c8304c63faf787a4ee3f`, analysis-source hash and each saved `RecoveryPlan.input_hash`. Show the fixed input assumptions instead of implying the numbers reflect live inventory. A changed receipt must invalidate the card rather than silently reuse cached values. If a later live version is approved, it must additionally bind current availability/allocation state: the existing problem fingerprint covers planning inputs, while concurrent reservations are checked separately by inventory. A historical fingerprint alone does not establish present availability.

## Measurable acceptance and regression limits

1. A reviewer can identify the missing fact, affected policy rule and conditional decision difference from the card without opening raw JSON. This requires a real usability review; no such human result is claimed yet.
2. All six rows exactly reproduce the retained receipt, including cash versus retained value, statuses, bounds and source pointers. At high labor, B and A must show the same optimal disposition; no invented difference may be displayed.
3. The card visibly says “Synthetic conditional scenarios; not a prediction or capture value.” Held is a genuine unresolved branch, not a zero-probability or hidden outcome.
4. Source and problem fingerprints are checked; stale, tampered or incomplete artifacts fail closed. A nonoptimal/UNKNOWN result cannot be labeled a proven best choice. Equal-valued alternative allocations are not presented as a unique optimum.
5. Opening, switching and exporting the card produces zero inference requests and zero evidence, verification, plan-proposal, reservation or inventory writes. Existing records and physical counts remain byte-for-byte or structurally unchanged as appropriate.
6. Existing append-only history, human correction, held-state exclusion, stale-evidence rejection and conflicting-reservation tests continue to pass. No domain validator or authorization rule is weakened to display a branch.
7. At desktop and mobile sizes, synthetic labels, unit labels and all three value columns stay readable. Reading the card does not require interpreting model confidence language or optimizer internals.

The first increment can remain an offline review artifact and be removed without changing runtime behavior. That gives it low regression risk and a clear stop condition if the explanation is confusing or crowds the judge demonstration. A live capture recommendation, multi-component ranking or expected-value feature should remain deferred until validated outcome data and a separately approved design justify it.

## Recommendation and approval gate

The benefit is concrete: explain why one observation changes the recovery plan while another only changes eligibility under a different cost assumption. This strengthens ReKit's evidence-to-decision story without claiming a new model capability or an unverified market advantage. The proposal is worth reviewing as a small explanatory artifact; it is not essential to the current validated workflow and should not delay genuine AMD qualification or final recording.

Owner approval is required before adding the card to the application or presentation. The approval decision should cover whether the additional explanation improves the limited demo time, where it will appear, and whether the fixed synthetic scope is acceptable. No implementation, Mission 07 work, AMD request, deployment, licensing change or public publication is authorized by this proposal.
