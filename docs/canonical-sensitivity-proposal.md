# Canonical labor sensitivity: a proposal for review

The frozen synthetic case has a verified decision change at **USD 1.70 per labor minute**, within the tested **USD 0.00–2.00/minute range in one-cent steps**. At USD 1.70, rebuilding and liquidation tie at USD 88.00. This is a conditional result for invented inputs, not a market threshold, realized savings or a general business recommendation.

No frontier has been added to the application or presentation. The proposed addition is a small, clearly labeled comparison around the tie, with a link to the retained solver receipt. Owner review should precede UI or slide expansion.

## Actual findings

| Labor assumption, USD/min | Two rebuilds, USD | Liquidate all three returns, USD | Globally optimal allocation within this fixture |
| --- | ---: | ---: | --- |
| 0.00 | 190.00 | 105.00 | Two rebuilds |
| 0.25, existing baseline | 175.00 | 102.50 | Two rebuilds |
| 1.69 | 88.60 | 88.10 | Two rebuilds |
| 1.70 | 88.00 | 88.00 | Tie: two rebuilds or all-return liquidation |
| 1.71 | 87.40 | 87.90 | All-return liquidation |
| 2.00, existing counterfactual | 70.00 | 85.00 | All-return liquidation |

Every tested integer rate from 0 through 169 cents selects the two-rebuild action pattern; rates 171 through 200 select whole-return liquidation. There are two equally valued physical pairings for the two kits. At 170 cents, both pairings and one liquidation allocation tie. The receipt retains all three optimal covers at the tie instead of treating whichever allocation CP-SAT returns as uniquely preferable.

The two displayed lines are `19000 − 60r` and `10500 − 10r`, measured in cents with `r` in cents/minute. Their crossing alone would not establish a global decision change. The result above additionally checks **all 210 complete feasible allocations**, including mixed rebuild, liquidation, retention, salvage and hold choices. There are **19 generated actions** (four each of hold, retain, salvage and rebuild, plus three whole-return liquidation actions), forming 73 distinct modeled-value/labor lines. None of the competing allocations has a higher value at any of the 201 tested rates.

## Frozen inputs and limits

- Four unique physical components from three synthetic returns, after the scripted B-to-A correction; two bodies and two compatible A adapters.
- One approved synthetic kit configuration: one body A and one adapter A; selling price USD 100, other processing cost USD 5 and 30 labor minutes per kit; demand at most two kits.
- Total labor capacity remains 60 minutes. The same catalog, policy, evidence, physical identities, return membership and donor estimates are held fixed.
- Liquidation assumes USD 80 for the body return with five labor minutes, USD 10 for adapter 001 with two minutes, and USD 15 for adapter 002 with three minutes.
- Retention values total USD 16, a noncash asset estimate. Salvage estimates remain USD 1 per component with zero specified salvage labor; all disposition approvals remain those in the frozen synthetic policy.
- Only `scenario.labor_cost_per_minute_cents` changes. The API accepts integer cents; the sweep makes no claim about fractional-cent inputs or rates outside 0–200 cents/minute. Mixed allocations can matter outside this range, so the result must not be extrapolated.
- The inputs omit sale probabilities, unrecorded costs and real recovery measurements. They do not establish functionality, safety, profitability in a real operation, or the expected value of an additional photograph.

## Reproduction and verification

Run from the repository root in the existing virtual environment, choosing a new output directory:

```powershell
.venv\Scripts\python.exe -B evaluation/run_canonical_sensitivity.py --output var/mission06-offline/block-d-canonical-sensitivity-NEW
.venv\Scripts\python.exe -B -m pytest tests/backend/test_canonical_sensitivity.py tests/backend/test_canonical_case.py tests/backend/test_recovery.py -q
```

The runner reads the frozen [canonical receipt](../var/mission06-offline/canonical-case-b1-first/receipt.json), SHA-256 `c405c532543cfbba0d32632025e0272a1f79c0bcdc88cc402ed9e4138ab507e7`. It refuses a changed receipt or changed source fixtures, validates the stored input fingerprint and writes only a new ignored offline evidence directory. It never modifies evidence stores, inventory, approvals, model outputs or inference settings. A clean clone requires the owner's preserved private receipt; the test suite constructs its own disposable canonical case instead.

The actual run uses the existing **OR-Tools CP-SAT 9.15.6755**, one worker and seed zero. All **201 sweep runs returned OPTIMAL**, with an exact matching best bound and zero absolute gap. Every full input snapshot, selected action, solver version, status, bound, gap, time limit and solver wall time is retained. The runner also verifies that candidate membership remains identical and candidate economics follow the expected linear change at every rate.

The final-source [Block D result](../var/mission06-offline/block-d-canonical-sensitivity-20261015-224735/receipt.json) has SHA-256 `cb565d5cdf87a46aa68bc02f3fe4b34da619c9d45d54c8304c63faf787a4ee3f`. It records analysis-source hash `efca1bce8f8cf7561a4f85bfe0997ab9eb84fe2eb4840ba30ae0dfbe80ddd697`. Earlier receipts remain preserved. Output files are nonsecret synthetic evidence in an ignored directory; the runner does not claim to apply private file ACLs. Reusing an existing output directory is rejected.

The independent exact-cover check follows the existing canonical test oracle. It enumerates unique complete covers and separately enforces physical exclusivity, full coverage, combined capacity and demand. It does not use CP-SAT or the production allocation validator. It **does share the existing candidate generator and source assumptions**, so it is an allocation cross-check, not independent validation of compatibility policy, business inputs or reality. No alternative optimization engine is introduced.

If any solve is unfinished or disagrees with the oracle, the runner records its actual status and suppresses the verified regime table. Tests cover that behavior with a zero-time UNKNOWN result, mixed allocations, all ties, preserved inputs, capacity/demand constraints, frozen-source rejection and overwrite protection.

Focused validation: **61 tests passed** across the sensitivity, canonical-case and recovery suites; the final-source rerun of all **15 sensitivity tests passed**. A draft test expected USD 74 instead of USD 76 in the separate held-state example; the independent solver/oracle agreement exposed that manual arithmetic mistake. The corrected expectation is USD 70 from the body return plus USD 6 from adapter 001. No production arithmetic was changed.

## Relation to decision-aware evidence research

The same receipt contains six additional read-only conditional solves at the two existing labor assumptions. They reuse the saved scripted B, review-required/held and corrected A evidence states for adapter 002, while keeping every other input fixed. They are hypothetical planning comparisons, not new human judgments, forecast outcomes or a capture recommendation. All six return OPTIMAL with matching exact-cover values and zero gap.

At USD 0.25/minute, the modeled totals are USD 107.75 for the historical B state (USD 101.75 estimated cash plus USD 6 retained value), USD 93.50 when that adapter is held (USD 87.50 cash plus USD 6 retained), and USD 175 for corrected A (two rebuilds). At USD 2/minute, both B and A yield the same optimal all-return liquidation value of USD 85; the held state yields USD 76 from liquidating only the other two returns. This distinguishes an evidence change that changes the global decision from one that changes rebuild compatibility but leaves the preferred disposition unchanged. It does not quantify the probability or cost of obtaining useful evidence.

## Proposed addition requiring review

Use a single compact comparison showing **USD 1.69 → rebuild, USD 1.70 → tie, USD 1.71 → liquidate**, with baseline and high-labor context available nearby. Caption it: “Modeled synthetic scenario. All 210 feasible allocations checked over integer labor rates USD 0.00–2.00/minute. Equal-value alternatives may exist.” Keep noncash retention separate from estimated cash, preserve the same-input explanation and link the complete receipt. Do not present an interpolation chart as additional CP-SAT runs or an out-of-range economic forecast.

This could strengthen the commercial story by showing a tested decision boundary and an explicit tie. Its benefit should be weighed against the seven-slide presentation's limited space. The current baseline/counterfactual demonstration already establishes the capability; this proposal is optional and has not changed that workflow.
