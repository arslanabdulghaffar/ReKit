import type { EconomicScenario, RecoveryAction, RecoveryPlan } from './types';
import { money } from './ui';

export function PlanAssumptions({ plan }: { plan: RecoveryPlan }) {
  const scenario = plan.problem.scenario;
  const sources = new Set(plan.problem.inventory.map(item => item.component.source_return_id));
  return <div className="plan-assumptions" aria-label="Assumptions behind this proposal">
    <h3>Assumptions behind this proposal</h3>
    <dl className="assumption-grid">
      <div><dt>Labor rate</dt><dd>{money(scenario.labor_cost_per_minute_cents, scenario.currency)} / minute</dd></div>
      <div><dt>Labor capacity</dt><dd>{scenario.labor_capacity_minutes === null ? 'No limit supplied' : `${scenario.labor_capacity_minutes} minutes`}</dd></div>
      <div><dt>Selected labor</dt><dd>{plan.labor_minutes === null ? 'No feasible selection reported' : `${plan.labor_minutes} minutes`}</dd></div>
      <div><dt>Snapshot pool</dt><dd>{plan.problem.inventory.length} components / {sources.size} source returns</dd></div>
    </dl>
    {scenario.kits.map(kit => <p className="muted" key={kit.configuration_id}>{kit.configuration_id}: {kit.demand_limit === null ? 'no demand limit supplied' : `demand limit ${kit.demand_limit}`}.</p>)}
    <small>Frozen scenario estimates. A changed assumption requires a new proposal.</small>
  </div>;
}

type Calculation = { kind: 'cash'; gross: number; labor: number; other: number } | { kind: 'retained'; value: number };
const safe = (value: number) => Number.isSafeInteger(value) && value >= 0;

// Explain an existing selected action only. This does not generate candidates,
// validate alternative feasibility, change the objective or authorize execution.
// Fail closed when the frozen inputs cannot reproduce the server's totals.
export function selectedCalculation(action: RecoveryAction, scenario: EconomicScenario): Calculation | null {
  if (!safe(scenario.labor_cost_per_minute_cents) || !safe(action.labor_minutes)) return null;
  let gross: number;
  let minutes: number;
  let other = 0;
  if (action.kind === 'rebuild') {
    const matches = scenario.kits.filter(kit => kit.configuration_id === action.configuration_id);
    if (matches.length !== 1) return null;
    const kit = matches[0]; gross = kit.selling_price_cents; minutes = kit.labor_minutes; other = kit.other_cost_cents;
  } else if (action.kind === 'liquidate') {
    const matches = scenario.returns.filter(record => record.return_id === action.source_return_id);
    if (matches.length !== 1) return null;
    const record = matches[0]; gross = record.liquidation_value_cents; minutes = record.liquidation_labor_minutes;
  } else if (action.kind === 'salvage' || action.kind === 'retain') {
    if (action.component_ids.length !== 1) return null;
    const matches = scenario.components.filter(component => component.physical_component_id === action.component_ids[0]);
    if (matches.length !== 1) return null;
    const component = matches[0];
    if (action.kind === 'retain') {
      return safe(component.donor_value_cents) && action.retained_value_cents === component.donor_value_cents
        && action.cash_recovery_cents === 0 && action.modeled_value_cents === component.donor_value_cents && action.labor_minutes === 0
        ? { kind: 'retained', value: component.donor_value_cents } : null;
    }
    gross = component.salvage_value_cents; minutes = component.salvage_labor_minutes;
  } else return null;
  const labor = minutes * scenario.labor_cost_per_minute_cents;
  if (![gross, minutes, other, labor].every(safe) || minutes !== action.labor_minutes || !Number.isSafeInteger(gross - labor - other)
    || gross - labor - other !== action.cash_recovery_cents || action.retained_value_cents !== 0 || action.modeled_value_cents !== action.cash_recovery_cents) return null;
  return { kind: 'cash', gross, labor, other };
}

export function SelectedActionCalculation({ action, scenario }: { action: RecoveryAction; scenario: EconomicScenario }) {
  const calculation = selectedCalculation(action, scenario);
  if (!calculation) return null;
  const format = (value: number) => money(value, scenario.currency);
  return <div className="action-calculation" aria-label="Selected action calculation">
    {calculation.kind === 'retained' ? <p><strong>Retained asset estimate: {format(calculation.value)}.</strong> Noncash inventory value; no sale is assumed.</p>
      : <p>Gross estimate {format(calculation.gross)} − labor {format(calculation.labor)} − other costs {format(calculation.other)} = <strong>net cash estimate {format(action.cash_recovery_cents)}.</strong></p>}
    <small>Explains this selected action from its frozen inputs. The server's recorded result remains authoritative.</small>
  </div>;
}
