import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import canonical from '../../evaluation/fixtures/canonical_case.json';
import recovery from '../../tests/fixtures/synthetic_recovery.json';
import { PlanAssumptions, SelectedActionCalculation, selectedCalculation } from './plan-summary';
import type { EconomicScenario, RecoveryAction, RecoveryPlan } from './types';

// Existing canonical scenario values, not independent human or business results.
const baseline: EconomicScenario = { ...recovery.scenario, scenario_estimate: true, returns: canonical.returns,
  components: recovery.scenario.components.map(item => ({ ...item, salvage_labor_minutes: 0 })) };
const changed = { ...baseline, labor_cost_per_minute_cents: canonical.controlled_labor_cost_per_minute_cents };
const rebuild: RecoveryAction = {
  action_id: 'synthetic-selected-rebuild', kind: 'rebuild', component_ids: ['synthetic-body-001', 'synthetic-adapter-001'],
  configuration_id: 'standard-kit', source_return_id: null, labor_minutes: 30, cash_recovery_cents: 8750,
  retained_value_cents: 0, modeled_value_cents: 8750, donor_opportunity_cost_cents: 800, incremental_vs_retain_cents: 7950, explanation: [],
};

it('explains the canonical baseline and changed-labor selected rebuild using recorded scenario amounts', () => {
  const before = JSON.stringify({ baseline, changed, rebuild });
  const normal = selectedCalculation(rebuild, baseline);
  const sensitive = selectedCalculation({ ...rebuild, cash_recovery_cents: 3500, modeled_value_cents: 3500 }, changed);
  expect(normal).toEqual({ kind: 'cash', gross: 10000, labor: 750, other: 500 });
  expect(sensitive).toEqual({ kind: 'cash', gross: 10000, labor: 6000, other: 500 });
  expect(rebuild.cash_recovery_cents * 2).toBe(canonical.expected.baseline.two_rebuilds);
  expect(3500 * 2).toBe(canonical.expected.changed_labor.two_rebuilds);
  expect(JSON.stringify({ baseline, changed, rebuild })).toBe(before);
  render(<SelectedActionCalculation action={rebuild} scenario={baseline} />);
  expect(screen.getByLabelText('Selected action calculation')).toHaveTextContent('Gross estimate USD 100.00 − labor USD 7.50 − other costs USD 5.00 = net cash estimate USD 87.50.');
});

it('explains each recorded liquidation allocation without assuming that a gross estimate is net recovery', () => {
  const values = [7000, 600, 900];
  const actions = canonical.returns.map((record, index): RecoveryAction => ({ ...rebuild, kind: 'liquidate',
    configuration_id: null, source_return_id: record.return_id, labor_minutes: record.liquidation_labor_minutes,
    cash_recovery_cents: values[index], modeled_value_cents: values[index] }));
  expect(actions.map(action => selectedCalculation(action, changed))).toEqual([
    { kind: 'cash', gross: 8000, labor: 1000, other: 0 },
    { kind: 'cash', gross: 1000, labor: 400, other: 0 },
    { kind: 'cash', gross: 1500, labor: 600, other: 0 },
  ]);
  expect(values.reduce((total, value) => total + value, 0)).toBe(canonical.expected.changed_labor.liquidate_all_returns);
});

it('keeps retained donor value explicitly noncash and does not subtract it again', () => {
  const item = baseline.components.find(item => item.physical_component_id === 'synthetic-body-001')!;
  const action: RecoveryAction = { ...rebuild, kind: 'retain', component_ids: [item.physical_component_id], configuration_id: null,
    labor_minutes: 0, cash_recovery_cents: 0, retained_value_cents: item.donor_value_cents, modeled_value_cents: item.donor_value_cents };
  expect(selectedCalculation(action, baseline)).toEqual({ kind: 'retained', value: 600 });
  expect(baseline.components.reduce((sum, item) => sum + item.donor_value_cents, 0)).toBe(canonical.expected.baseline.retain_all);
  render(<SelectedActionCalculation action={action} scenario={baseline} />);
  expect(screen.getByLabelText('Selected action calculation')).toHaveTextContent('Retained asset estimate: USD 6.00. Noncash inventory value; no sale is assumed.');
  expect(screen.queryByText(/net cash estimate/)).not.toBeInTheDocument();
});

it('handles a permitted salvage calculation and negative cash without making a feasibility claim', () => {
  const item = baseline.components[0];
  const scenario = { ...baseline, components: [{ ...item, salvage_value_cents: 100, salvage_labor_minutes: 5 }] };
  const action: RecoveryAction = { ...rebuild, kind: 'salvage', component_ids: [item.physical_component_id], configuration_id: null,
    labor_minutes: 5, cash_recovery_cents: -25, modeled_value_cents: -25 };
  expect(selectedCalculation(action, scenario)).toEqual({ kind: 'cash', gross: 100, labor: 125, other: 0 });
  render(<SelectedActionCalculation action={action} scenario={scenario} />);
  expect(screen.getByLabelText('Selected action calculation')).toHaveTextContent('net cash estimate USD -0.25.');
  expect(screen.queryByText(/feasible|optimal/)).not.toBeInTheDocument();
});

it.each(['missing', 'ambiguous', 'labor', 'cash', 'retained', 'modeled', 'unsafe'] as const)('suppresses a calculation with %s source/result mismatch', reason => {
  const scenario = structuredClone(baseline); const action = { ...rebuild };
  if (reason === 'missing') scenario.kits = [];
  if (reason === 'ambiguous') scenario.kits.push({ ...scenario.kits[0] });
  if (reason === 'labor') action.labor_minutes += 1;
  if (reason === 'cash') action.cash_recovery_cents += 1;
  if (reason === 'retained') action.retained_value_cents = 1;
  if (reason === 'modeled') action.modeled_value_cents += 1;
  if (reason === 'unsafe') scenario.labor_cost_per_minute_cents = Number.MAX_SAFE_INTEGER;
  expect(selectedCalculation(action, scenario)).toBeNull();
  render(<SelectedActionCalculation action={action} scenario={scenario} />);
  expect(screen.queryByLabelText('Selected action calculation')).not.toBeInTheDocument();
});

it('does not invent a cash calculation for held components or ambiguous multi-component retention', () => {
  expect(selectedCalculation({ ...rebuild, kind: 'hold' }, baseline)).toBeNull();
  expect(selectedCalculation({ ...rebuild, kind: 'retain' }, baseline)).toBeNull();
});

it('shows immutable labor and pool assumptions without an editable form or alternative claims', () => {
  const plan = { labor_minutes: 60, problem: { scenario: baseline, inventory: recovery.components.map(record => ({ component: record.component })) } } as RecoveryPlan;
  const before = JSON.stringify(plan);
  render(<PlanAssumptions plan={plan} />);
  expect(screen.getByLabelText('Assumptions behind this proposal')).toHaveTextContent('USD 0.25 / minute');
  expect(screen.getAllByText('60 minutes')).toHaveLength(2);
  expect(screen.getByText('4 components / 3 source returns')).toBeInTheDocument();
  expect(screen.getByText('standard-kit: demand limit 2.')).toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(JSON.stringify(plan)).toBe(before);
});

it('distinguishes absent limits and missing feasible selection from zero labor', () => {
  const scenario = { ...baseline, labor_capacity_minutes: null, kits: baseline.kits.map(kit => ({ ...kit, demand_limit: null })) };
  const plan = { labor_minutes: null, problem: { scenario, inventory: [] } } as unknown as RecoveryPlan;
  render(<PlanAssumptions plan={plan} />);
  expect(screen.getByText('No limit supplied')).toBeInTheDocument();
  expect(screen.getByText('No feasible selection reported')).toBeInTheDocument();
  expect(screen.getByText('standard-kit: no demand limit supplied.')).toBeInTheDocument();
  expect(screen.queryByText('0 minutes')).not.toBeInTheDocument();
});
