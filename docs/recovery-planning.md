# Recovery planning and scenario economics

The planner uses OR-Tools CP-SAT on CPU. Inputs are a validated catalog,
operator-verified/held inventory snapshots, full registered return membership,
an approved disposition policy, and explicit economic estimates. It does not
perform inference, approve a plan, reserve inventory, or execute a sale.

All money is integer cents in one stated currency. The scenario records its ID,
valuation date, description, labor rate, kit selling prices/costs, donor values,
and any liquidation/salvage values. Labor capacity and demand limits may be
omitted explicitly. Every supplied physical component needs a donor estimate,
including an explicit zero when no donor value is assumed. Unknown or held
items receive only a zero-value hold action.

## Decisions and constraints

Candidate actions are complete-kit rebuild, permitted whole-return liquidation,
donor retention, permitted component salvage, and hold. A rebuild uses exact BOM
quantities and only approved revisions/visible conditions. Salvage and
liquidation need explicit disposition permission and allowed visible condition.
Identity verification alone does not grant kit compatibility or certify hidden
function/safety.

CP-SAT selects exactly one disposition for each supplied physical component.
This prevents two kits from sharing one object. A liquidation action consumes
every registered member of its return; if even one member is outside the
available planning pool or is held, that action cannot be generated. Selecting
it therefore conflicts with every separate use of those parts. Full return
membership must come from the authoritative registry, not a filtered photo list.

The solver enforces total labor capacity and per-configuration kit demand.
Candidate enumeration is complete within a limit of 10,000 actions and 100
supplied components. An oversized problem fails explicitly rather than silently
discarding options. Integer coefficient ranges are checked before solving.

## Donor opportunity cost

The objective is total modeled disposition value. Rebuild/liquidation/salvage
contribute estimated cash proceeds net of specified costs; retained components
contribute estimated noncash inventory value. Holds contribute zero. Neither
category is reported as realized business revenue.

For example, two parts valued at 600 cents each as donors compete with a kit
priced at 2,000 cents, requiring 500 cents of labor and 100 cents of other costs.
The kit has 1,400 cents of modeled cash recovery. Donor retention is 1,200 cents
of modeled asset value; the rebuild improves this particular alternative by
200 cents. The objective counts the selected 1,400 cents once. It does not
subtract the 1,200-cent donor value again while also treating retention as an
alternative. Whole-return liquidation and salvage values compete globally too.

Each action exposes its donor opportunity cost and incremental value versus
retaining those donors. These comparisons explain the scenario; they are not
additional debits in the objective. A profitable-looking rebuild may still lose
to a better feasible disposition or to limited labor/demand.

## Results and explanations

The result preserves the full input snapshot and its hash, selected actions,
cash and retained-value subtotals, labor, candidate rejection reasons, and
solver version/settings. The [CP-SAT status](https://developers.google.com/optimization/cp/cp_solver)
is reported as returned: OPTIMAL, FEASIBLE, INFEASIBLE, MODEL_INVALID, or UNKNOWN.
Only a feasible solution supplies recovery totals and selected actions. A
timeout without a solution does not become an invented hold plan or profit.

The model uses one solver worker and records its seed and time limit. A feasible
time-limited result is not called optimal. Bounds and absolute gaps are reported
when a solution exists. Equal-value allocations may differ without changing the
modeled objective; no claim of a unique best plan is made.

Candidate rejections name missing BOM quantities, revision/condition rules, or
disposition policy failures. Alternative explanations distinguish a conflict
with the current selection from global infeasibility: replacing selected
actions may make an alternative possible. Arithmetic and constraints produce
these explanations, without an LLM. Re-solving with changed prices or labor
assumptions provides sensitivity analysis.

Tests compare small CP-SAT results with an independent exhaustive subset search
and cover conflicts, incomplete returns, resource limits, uncertainty, economic
trade-offs, and timeout status. All fixtures and values are synthetic. No AMD
performance or visual-model accuracy is measured by these CPU tests.
