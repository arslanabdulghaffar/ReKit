import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import catalogFixture from '../../tests/fixtures/synthetic_catalog.json';
import { ApiClient } from './api';
import { ObservationSource, VerificationSummary, originalImageId } from './evidence-history';
import { Stock } from './recovery';
import type { Catalog, EvidenceHistory, ImageAsset, Verification, WorkspaceData } from './types';

// These are UI contract fixtures, not independent human review judgments.
const component = { physical_component_id: 'synthetic-adapter', source_return_id: 'synthetic-return', registered_at: '2026-10-15T00:00:00Z' };
const assets: ImageAsset[] = ['overview', 'closeup'].map((name, index) => ({
  asset_id: `synthetic-${name}`, physical_component_id: component.physical_component_id, return_id: component.source_return_id,
  sha256: String(index).repeat(64), byte_size: 100, media_type: 'image/png', width: 80, height: 60,
  received_at: component.registered_at, uploaded_by: 'synthetic-operator', observation_id: `observation-${name}`, availability: 'available',
}));
const previous: Verification = {
  verification_id: 'assertion-before', physical_component_id: component.physical_component_id,
  identity: { component_type_id: 'adapter', revision: 'B' }, operator_id: 'synthetic-reviewer-before',
  verified_at: component.registered_at, evidence_observation_ids: [assets[0].observation_id],
  visible_condition: 'unknown', reason: 'Initial synthetic ambiguous interpretation.', supersedes_verification_id: null,
};
const current: Verification = { ...previous, verification_id: 'assertion-after', identity: { component_type_id: 'adapter', revision: 'A' },
  operator_id: 'synthetic-reviewer-after', evidence_observation_ids: assets.map(asset => asset.observation_id),
  visible_condition: 'acceptable', reason: 'Synthetic close-up corrects the visible revision.', supersedes_verification_id: previous.verification_id };
const observation = (asset: ImageAsset, sequence: number) => ({ sequence, kind: 'observation', event_id: asset.observation_id,
  recorded_at: component.registered_at, payload: { observation_id: asset.observation_id,
    physical_component_id: component.physical_component_id, source_return_id: component.source_return_id,
    evidence_reference: `asset:${asset.asset_id}`, source: 'operator' } });
const assertion = (verification: Verification, sequence: number) => ({ sequence, kind: 'verification', event_id: verification.verification_id,
  recorded_at: component.registered_at, payload: { ...verification } });
function history(): EvidenceHistory {
  return { component, current: { physical_component_id: component.physical_component_id, version: 5, state: 'verified', verification: current, unresolved_reasons: [] },
    events: [observation(assets[0], 10), assertion(previous, 50), observation(assets[1], 200), assertion(current, 500)] };
}

it('compares explicit superseding assertions and uses component event positions, not global sequences', () => {
  const value = history();
  const frozen = JSON.stringify(value);
  render(<VerificationSummary history={value} assets={assets} />);
  expect(screen.getByRole('heading', { name: 'Human correction summary' })).toBeInTheDocument();
  expect(screen.getByText('Evidence version 3 at assertion')).toBeInTheDocument();
  expect(screen.getByText('Evidence version 5 at assertion')).toBeInTheDocument();
  expect(screen.queryByText('Evidence version 500 at assertion')).not.toBeInTheDocument();
  const revision = screen.getByRole('rowheader', { name: /Revision changed/ }).closest('tr')!;
  expect(within(revision).getAllByRole('cell').map(cell => cell.textContent)).toEqual(['B', 'A']);
  expect(screen.getByText(previous.reason)).toBeInTheDocument();
  expect(screen.getByText(current.reason)).toBeInTheDocument();
  expect(screen.getAllByText('Added at evidence version 4 · observation-closeup')).toHaveLength(1);
  const addedCitation = screen.getByText('Newly cited in this correction');
  expect(addedCitation.parentElement).toContainElement(screen.getByRole('link', { name: 'View original Image 2' }));
  expect(JSON.stringify(value)).toBe(frozen);
});

it('navigates supporting observations to the original managed image without fetching external evidence', async () => {
  const user = userEvent.setup();
  render(<><div id={originalImageId(assets[1].asset_id)} tabIndex={-1}>Controlled original close-up</div><VerificationSummary history={history()} assets={assets} /></>);
  const link = screen.getByRole('link', { name: 'View original Image 2' });
  expect(link).toHaveAttribute('href', `#${originalImageId(assets[1].asset_id)}`);
  await user.click(link);
  expect(screen.getByText('Controlled original close-up')).toHaveFocus();
});

it('keeps the last assertion historical when a new observation changes the evidence version', () => {
  const value = history();
  value.events.push({ ...observation(assets[1], 900), event_id: 'new-observation' });
  value.current = { ...value.current, version: 6, state: 'review_required', unresolved_reasons: ['New evidence requires review.'] };
  render(<VerificationSummary history={value} assets={assets} />);
  expect(screen.getByText(/latest recorded human assertion, not a current approval/)).toHaveTextContent('Evidence version 6 requires fresh review.');
  expect(screen.getByText('Evidence version 5 at assertion')).toBeInTheDocument();
  expect(screen.queryByText('Evidence version 6 at assertion')).not.toBeInTheDocument();
});

it('does not invent prior values or assertion versions when a history response is incomplete', () => {
  const value = history();
  value.events = value.events.filter(event => event.event_id !== previous.verification_id);
  render(<VerificationSummary history={value} assets={assets} />);
  expect(screen.getByText(/Superseded assertion assertion-before is unavailable/)).toBeInTheDocument();
  expect(screen.getByText('Assertion evidence version unavailable')).toBeInTheDocument();
  expect(screen.queryByRole('columnheader', { name: 'Previous assertion' })).not.toBeInTheDocument();
  expect(screen.queryByText(previous.reason)).not.toBeInTheDocument();
  expect(screen.queryByText('Newly cited in this correction')).not.toBeInTheDocument();
});

it('does not link external, missing-record, or different-component evidence as a managed original', () => {
  const value = history();
  value.events[0].payload.evidence_reference = 'https://private.invalid/not-to-fetch';
  render(<><ObservationSource history={value} observationId={assets[0].observation_id} assets={[{ ...assets[0], physical_component_id: 'different-component' }]} />
    <ObservationSource history={value} observationId="not-in-history" assets={assets} /></>);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getAllByText('External or unavailable evidence')).toHaveLength(2);
  expect(screen.queryByText('https://private.invalid/not-to-fetch')).not.toBeInTheDocument();
});

it('preserves first-verification semantics without fabricating a correction', () => {
  const value = history();
  value.events = value.events.slice(0, 2);
  value.current = { ...value.current, version: 3, verification: previous };
  render(<VerificationSummary history={value} assets={assets} />);
  expect(screen.getByRole('heading', { name: 'Latest human verification' })).toBeInTheDocument();
  expect(screen.queryByText('Human correction summary')).not.toBeInTheDocument();
  expect(screen.queryByText('Changed')).not.toBeInTheDocument();
  expect(screen.queryByText('Newly cited in this correction')).not.toBeInTheDocument();
});

it('labels a newly cited older observation without claiming it is a newly captured image', () => {
  const value = history();
  value.events = [observation(assets[0], 10), observation(assets[1], 20), assertion(previous, 50), assertion(current, 500)];
  render(<VerificationSummary history={value} assets={assets} />);
  expect(screen.getByText('Newly cited in this correction')).toBeInTheDocument();
  expect(screen.getByText('Added at evidence version 3 · observation-closeup')).toBeInTheDocument();
  expect(screen.queryByText(/newly captured|new image/i)).not.toBeInTheDocument();
});

it.each(['reference', 'return', 'component'] as const)('does not navigate a contradictory observation %s association', field => {
  const value = history();
  if (field === 'reference') value.events[0].payload.evidence_reference = `asset:${assets[1].asset_id}`;
  if (field === 'return') value.events[0].payload.source_return_id = 'different-return';
  if (field === 'component') value.events[0].payload.physical_component_id = 'different-component';
  render(<ObservationSource history={value} observationId={assets[0].observation_id} assets={assets} />);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByText('External or unavailable evidence')).toBeInTheDocument();
});

it('links an independently recorded model observation only through its explicit matching original asset reference', () => {
  const value = history();
  value.events.push({ ...observation(assets[0], 700), event_id: 'model-observation', payload: { ...value.events[0].payload, source: 'model', observation_id: 'model-observation' } });
  value.current.version = 6;
  render(<ObservationSource history={value} observationId="model-observation" assets={assets} />);
  expect(screen.getByRole('link', { name: 'View original Image 1' })).toHaveAttribute('href', `#${originalImageId(assets[0].asset_id)}`);
});

it('connects final kit lineage to existing evidence and audit views without treating current versions as approved snapshots', async () => {
  const data: WorkspaceData = { catalog: catalogFixture as Catalog, batches: [], returns: [], plans: [], inventory: {
    items: [{ item: { component, evidence: history().current, eligibility: 'eligible' }, availability: 'consumed', plan_id: 'synthetic-plan', action_id: 'synthetic-action' }],
    completed_kits: [{ completed_kit_id: 'synthetic-kit', plan_id: 'synthetic-plan', action_id: 'synthetic-action', configuration_id: 'standard-kit',
      component_ids: [component.physical_component_id, 'unavailable-component'], operator_id: 'synthetic-executor', completed_at: component.registered_at,
      evidence_references: ['synthetic:completion-reference'] }],
  } };
  const onReview = vi.fn(); const onOpenPlan = vi.fn(); const user = userEvent.setup();
  render(<Stock api={new ApiClient('controlled-ui-test-token')} actor={{ actor_id: 'synthetic-viewer', kind: 'human', roles: ['viewer'] }} data={data}
    refresh={vi.fn(async () => {})} onError={vi.fn()} onMessage={vi.fn()} onReview={onReview} onOpenPlan={onOpenPlan} />);
  expect(screen.getByText('Source return synthetic-return')).toBeInTheDocument();
  expect(screen.getByText('Current evidence version 5 · consumed')).toBeInTheDocument();
  expect(screen.getByText(/recovery audit retains the approved plan's original evidence versions/)).toBeInTheDocument();
  expect(screen.getByText(/Component details unavailable in this inventory response/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'View evidence for synthetic-adapter' }));
  expect(onReview).toHaveBeenCalledExactlyOnceWith(component.physical_component_id);
  await user.click(screen.getByRole('button', { name: /Open recovery audit/ }));
  expect(onOpenPlan).toHaveBeenCalledExactlyOnceWith('synthetic-plan');
});
