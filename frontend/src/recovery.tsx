import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { idPath, newId } from './api';
import type { WorkspaceProps } from './workspace';
import type { AuditRecord, EconomicScenario, RecoveryAction, StoredPlan } from './types';
import { Badge, Empty, Field, Notice, Section, can, dateTime, isConflict, money, parseInteger } from './ui';

function IntegerInput({ name, required = true, value }: { name: string; required?: boolean; value?: number }) { return <input name={name} type="number" min="0" max="1000000000" step="1" required={required} defaultValue={value} placeholder={required ? 'Required' : 'No limit'} />; }
const consumes = (action: RecoveryAction) => ['rebuild', 'salvage', 'liquidate'].includes(action.kind);

export function Planning({ api, actor, data, refresh, onError, onMessage, onOpenPlan }: WorkspaceProps & { onOpenPlan: (id: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [kitIds, setKitIds] = useState<string[]>([]);
  const pool = data.inventory.items.filter(entry => ['available', 'held'].includes(entry.availability));
  const returns = data.returns.filter(record => data.inventory.items.some(entry => entry.item.component.source_return_id === record.return_id));
  async function plan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true);
    try {
      const int = (key: string) => parseInteger(form.get(key), key)!;
      const optional = (key: string) => parseInteger(form.get(key), key, true);
      const scenario: EconomicScenario = {
        scenario_id: newId('scenario'), description: String(form.get('description')).trim(), currency: String(form.get('currency')),
        valuation_date: String(form.get('valuation_date')), labor_cost_per_minute_cents: int('labor_rate'), labor_capacity_minutes: optional('capacity'), scenario_estimate: true,
        kits: kitIds.map(id => ({ configuration_id: id, selling_price_cents: int(`price-${id}`), labor_minutes: int(`labor-${id}`), other_cost_cents: int(`cost-${id}`), demand_limit: optional(`demand-${id}`) })),
        components: pool.map(entry => { const id = entry.item.component.physical_component_id; return { physical_component_id: id, donor_value_cents: int(`donor-${id}`), salvage_value_cents: int(`salvage-${id}`), salvage_labor_minutes: int(`salvage-labor-${id}`) }; }),
        returns: returns.map(record => ({ return_id: record.return_id, liquidation_value_cents: int(`liquidation-${record.return_id}`), liquidation_labor_minutes: int(`liquidation-labor-${record.return_id}`) })),
      };
      const stored = await api.post<StoredPlan>('/plans', { scenario, settings: { max_time_seconds: 10, random_seed: 0 } });
      await refresh(); onMessage('Recovery proposal generated from the current inventory and server-approved policies.'); onOpenPlan(stored.plan.plan_id);
    } catch (error) { onError(error); if (isConflict(error)) await refresh().catch(onError); }
    finally { setBusy(false); }
  }
  return <>
    <div className="page-intro"><h2>Give the recovery plan real assumptions.</h2><p>Compare complete kits, retained donors, and permitted dispositions. The server enforces compatibility, physical uniqueness, labor, and demand.</p></div>
    {!can(actor, 'planner') && <Notice>Planner role required to generate proposals. Existing plans remain available for review.</Notice>}
    <form onSubmit={plan}><fieldset disabled={busy || !can(actor, 'planner')}>
      <Section title="Economic scenario" eyebrow="ESTIMATES, NOT REALIZED REVENUE"><div className="form-grid three"><Field label="Scenario description"><input name="description" required maxLength={2048} placeholder="Describe the source and purpose of these estimates" /></Field><Field label="Currency" hint="All monetary fields use integer cents: 100 cents = 1 currency unit."><select name="currency"><option>USD</option><option>EUR</option><option>GBP</option></select></Field><Field label="Valuation date"><input name="valuation_date" type="date" required defaultValue={new Date().toISOString().slice(0, 10)} /></Field><Field label="Labor cost per minute (cents)"><IntegerInput name="labor_rate" /></Field><Field label="Labor capacity (minutes)" hint="This proposal only; not a shared schedule across plans."><IntegerInput name="capacity" required={false} /></Field></div></Section>
      <Section title="Kit recovery estimates" eyebrow="APPROVED CATALOG CONFIGURATIONS">
        {data.catalog.configurations.map(config => <div key={config.configuration_id} className="estimate-block"><label className="checkbox"><input type="checkbox" checked={kitIds.includes(config.configuration_id)} onChange={event => setKitIds(ids => event.target.checked ? [...ids, config.configuration_id] : ids.filter(id => id !== config.configuration_id))} /><span><strong>Include {config.configuration_id}</strong><small>BOM: {config.bom.map(line => `${line.quantity} × ${line.component_type_id}`).join(' + ')}</small></span></label>{kitIds.includes(config.configuration_id) && <div className="form-grid four"><Field label={`Selling price (cents) — ${config.configuration_id}`}><IntegerInput name={`price-${config.configuration_id}`} /></Field><Field label={`Rebuild labor (minutes) — ${config.configuration_id}`}><IntegerInput name={`labor-${config.configuration_id}`} /></Field><Field label={`Other costs (cents) — ${config.configuration_id}`}><IntegerInput name={`cost-${config.configuration_id}`} /></Field><Field label={`Demand limit — ${config.configuration_id}`}><IntegerInput name={`demand-${config.configuration_id}`} required={false} /></Field></div>}</div>)}
      </Section>
      <Section title="Physical component economics" aside={<span>{pool.length} unallocated items</span>}><p className="muted">Supply a donor value for every available or held component. Retention is noncash inventory value. A held component remains held regardless of its entered estimate. Zero salvage values below explicitly value that option at zero; policy permission is still required.</p>{pool.length ? <div className="table-scroll"><table><thead><tr><th>Physical component / return</th><th>Donor value (cents)</th><th>Salvage value (cents)</th><th>Salvage labor (min)</th></tr></thead><tbody>{pool.map(entry => { const id = entry.item.component.physical_component_id; return <tr key={id}><td><strong>{id}</strong><small>{entry.item.component.source_return_id}</small><Badge value={entry.availability} /></td><td><label className="sr-only" htmlFor={`donor-${id}`}>Donor value (cents) — {id}</label><input id={`donor-${id}`} name={`donor-${id}`} type="number" min="0" max="1000000000" step="1" required placeholder="Required" /></td><td><Field label={`Salvage value (cents) — ${id}`}><IntegerInput name={`salvage-${id}`} value={0} /></Field></td><td><Field label={`Salvage labor (minutes) — ${id}`}><IntegerInput name={`salvage-labor-${id}`} value={0} /></Field></td></tr>; })}</tbody></table></div> : <Empty>No unallocated components. Add and review returned components first.</Empty>}</Section>
      <Section title="Whole-return liquidation"><p className="muted">Liquidation requires explicit server policy permission and every registered component of the return to be available and eligible. A value alone never grants permission.</p>{returns.map(record => <div className="form-grid three estimate-block" key={record.return_id}><strong>{record.return_id}</strong><Field label={`Liquidation value (cents) — ${record.return_id}`}><IntegerInput name={`liquidation-${record.return_id}`} value={0} /></Field><Field label={`Liquidation labor (minutes) — ${record.return_id}`}><IntegerInput name={`liquidation-labor-${record.return_id}`} value={0} /></Field></div>)}</Section>
      <div className="action-bar"><div><strong>Ready to compare the options?</strong><p>No stock is reserved until an authorized human approves the proposal.</p></div><button className="primary" disabled={busy || !can(actor, 'planner') || !pool.length}>{busy ? 'Solving recovery plan…' : 'Generate recovery plan'}</button></div>
    </fieldset></form>
    <PlanList data={data} onOpenPlan={onOpenPlan} />
  </>;
}

function PlanList({ data, onOpenPlan }: Pick<WorkspaceProps, 'data'> & { onOpenPlan: (id: string) => void }) {
  return <Section title="Recent recovery plans" aside={<small>Latest 50 proposals</small>}>{data.plans.length ? <div className="table-scroll"><table><thead><tr><th>Scenario</th><th>State</th><th>Solver</th><th>Modeled value</th><th>Created</th><th /></tr></thead><tbody>{data.plans.map(plan => <tr key={plan.plan_id}><td><strong>{plan.description}</strong><code>{plan.plan_id}</code></td><td><Badge value={plan.state} /></td><td><Badge value={plan.status} /></td><td>{money(plan.modeled_value_cents, plan.currency)}</td><td>{dateTime(plan.created_at)}</td><td><button className="text-button" onClick={() => onOpenPlan(plan.plan_id)}>Open plan</button></td></tr>)}</tbody></table></div> : <Empty>No plans have been proposed yet.</Empty>}</Section>;
}

export function Execution(props: WorkspaceProps & { planId: string; onSelect: (id: string) => void }) {
  const { api, actor, data, refresh, onError, onMessage, planId, onSelect } = props;
  const [stored, setStored] = useState<StoredPlan | null>(null);
  const [audit, setAudit] = useState<AuditRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('');
  const pending = useRef<{ key: string; body: unknown } | null>(null);
  async function load() {
    const [stored, audit] = await Promise.all([api.get<StoredPlan>(`/plans/${idPath(planId)}`), api.get<AuditRecord[]>(`/plans/${idPath(planId)}/audit`)]);
    setStored(stored); setAudit(audit);
  }
  useEffect(() => {
    let current = true; setStored(null); setAudit([]); setReason(''); pending.current = null;
    if (planId) void Promise.all([api.get<StoredPlan>(`/plans/${idPath(planId)}`), api.get<AuditRecord[]>(`/plans/${idPath(planId)}/audit`)]).then(([stored, audit]) => { if (current) { setStored(stored); setAudit(audit); } }).catch(error => { if (current) onError(error); });
    return () => { current = false; };
  }, [planId, api]);
  async function transition(kind: 'approve' | 'cancel') {
    if (!stored || !reason.trim()) return; setBusy(true);
    const key = JSON.stringify([kind, planId, stored.version, reason]);
    if (pending.current?.key !== key) pending.current = { key, body: { operation_id: newId(kind), expected_version: stored.version, reason: reason.trim() } };
    try { const updated = await api.post<StoredPlan>(`/plans/${idPath(planId)}/${kind}`, pending.current.body); setStored(updated); pending.current = null; await load(); await refresh(); setReason(''); onMessage(kind === 'approve' ? 'Approval recorded. Consuming actions reserved their physical components atomically.' : 'Plan cancelled. Unconsumed reservations released.'); }
    catch (error) { onError(error); if (isConflict(error)) { await load().catch(onError); await refresh().catch(onError); } }
    finally { setBusy(false); }
  }
  async function completed(updated: StoredPlan) { setStored(updated); await load(); await refresh(); onMessage('Action completion recorded. Physical identities and kit lineage are retained.'); }
  if (!planId) return <><div className="page-intro"><h2>From approved proposal to traceable kit.</h2><p>Approval reserves components. Completion records an explicit operator-confirmed disposition.</p></div><PlanList data={data} onOpenPlan={onSelect} /><Section title="Open a specific plan"><form onSubmit={event => { event.preventDefault(); onSelect(String(new FormData(event.currentTarget).get('plan_id'))); }}><Field label="Plan ID"><input name="plan_id" required /></Field><button className="secondary">Load plan</button></form></Section></>;
  if (!stored) return <Empty>Loading the selected recovery plan… <button className="text-button" onClick={() => onSelect('')}>Back to plans</button></Empty>;
  const plan = stored.plan; const currency = plan.problem.scenario.currency;
  return <>
    <div className="section-heading"><button className="text-button" disabled={busy} onClick={() => onSelect('')}>← All plans</button><button className="secondary" disabled={busy} onClick={() => void load().then(refresh).catch(onError)}>Refresh plan</button></div>
    <Section title={plan.problem.scenario.description} eyebrow="IMMUTABLE SCENARIO PROPOSAL"><div className="context-line"><code>{plan.plan_id}</code><Badge value={stored.state} /><Badge value={plan.status} /><span>Plan version {stored.version}</span></div><div className="value-grid"><div><small>Modeled total</small><strong>{money(plan.modeled_value_cents, currency)}</strong></div><div><small>Estimated net cash recovery</small><strong>{money(plan.cash_recovery_cents, currency)}</strong></div><div><small>Retained donor asset value</small><strong>{money(plan.retained_value_cents, currency)}</strong></div></div><p className="muted">These are scenario estimates, not realized revenue or guaranteed profit. Retained inventory is noncash.</p><div className="solver-line"><span>Labor {plan.labor_minutes ?? '—'} min</span><span>Best bound {money(plan.best_bound_cents, currency)}</span><span>Gap {money(plan.absolute_gap_cents, currency)}</span><span>{plan.number_of_candidates} candidates</span><span>CP-SAT {plan.solver_version} · {plan.wall_time_seconds.toFixed(3)} s</span></div>{plan.explanations.map((text, index) => <p className="muted" key={index}>{text}</p>)}<details><summary>Scenario and policy snapshot</summary><p>Catalog {plan.problem.catalog.catalog_id} v{plan.problem.catalog.version} · Disposition policy {plan.problem.policy.policy_id} v{plan.problem.policy.version}</p><code>Input fingerprint {plan.input_hash}</code><pre>{JSON.stringify(plan.problem.scenario, null, 2)}</pre></details></Section>
    <Section title="Approval & reservation"><p>A human approval reserves all consuming actions together. Cancellation is available only before any action is completed.</p>{!can(actor, 'approver') && <Notice>A human approver role is required for approval or cancellation.</Notice>}<Field label="Approval or cancellation reason"><textarea value={reason} onChange={event => setReason(event.target.value)} rows={2} maxLength={2048} placeholder="Record the operational reason for this decision" /></Field><div className="button-row"><button className="primary" disabled={busy || !can(actor, 'approver') || !reason.trim() || stored.state !== 'proposed' || !['OPTIMAL', 'FEASIBLE'].includes(plan.status)} onClick={() => void transition('approve')}>Approve and reserve</button><button className="danger-button" disabled={busy || !can(actor, 'approver') || !reason.trim() || !['proposed', 'approved'].includes(stored.state) || stored.completed_action_ids.length > 0} onClick={() => void transition('cancel')}>Cancel plan</button></div></Section>
    <Section title="Selected dispositions" aside={<span>{plan.selected_actions.length} actions</span>}>{!plan.selected_actions.length && <Empty>No selected actions. A solver without a feasible solution cannot be approved.</Empty>}{plan.selected_actions.map(action => <article className="action-card" key={action.action_id}>
      <div className="section-heading"><div className="context-line"><Badge value={action.kind} /><h3>{action.configuration_id ?? action.source_return_id ?? action.component_ids[0]}</h3></div>{stored.completed_action_ids.includes(action.action_id) && <Badge value="completed" />}</div>
      <div className="action-facts"><span>Modeled <strong>{money(action.modeled_value_cents, currency)}</strong></span><span>Donor alternative <strong>{money(action.donor_opportunity_cost_cents, currency)}</strong></span><span>Increment vs. retaining <strong>{money(action.incremental_vs_retain_cents, currency)}</strong></span><span>Labor <strong>{action.labor_minutes} min</strong></span></div>
      <ul className="lineage">{action.component_ids.map(id => { const item = plan.problem.inventory.find(item => item.component.physical_component_id === id); return <li key={id}><code>{id}</code><span>from {item?.component.source_return_id ?? 'unknown'} · {item?.evidence.verification?.identity.component_type_id ?? 'unverified'} {item?.evidence.verification?.identity.revision ?? ''} · evidence v{item?.evidence.version ?? '?'}</span></li>; })}</ul>
      {action.explanation.map((text, index) => <p className="muted" key={index}>{text}</p>)}
      {consumes(action) && stored.state === 'approved' && !stored.completed_action_ids.includes(action.action_id) && <Completion {...props} stored={stored} action={action} onComplete={completed} onReload={load} operationBusy={busy} onBusy={setBusy} />}
    </article>)}</Section>
    <Section title="Alternatives & exclusions"><p>The donor values above compare each selection with retaining those components. Server exclusions explain unavailable options; changing economic assumptions creates a new proposal.</p>{plan.rejections.length ? plan.rejections.map((rejection, index) => <details key={index}><summary>{rejection.subject}</summary><ul>{rejection.reasons.map((reason, number) => <li key={number}>{reason}</li>)}</ul></details>) : <Empty>No additional candidate exclusions were reported. Equal-value solutions may exist.</Empty>}</Section>
    <Section title="Audit trail"><ol className="audit-list">{audit.map(record => <li key={record.sequence}><div><Badge value={record.kind} /><strong>{record.operator_id}</strong><small>{dateTime(record.recorded_at)} · plan v{record.plan_version}</small></div><p>{record.reason}</p><code>{record.operation_id}</code></li>)}</ol></Section>
  </>;
}

function Completion({ api, actor, onError, refresh, stored, action, onComplete, onReload, operationBusy, onBusy }: WorkspaceProps & { stored: StoredPlan; action: RecoveryAction; onComplete: (stored: StoredPlan) => Promise<void>; onReload: () => Promise<void>; operationBusy: boolean; onBusy: (busy: boolean) => void }) {
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const pending = useRef<{ key: string; body: unknown } | null>(null);
  async function complete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!confirmed || checked.length !== action.component_ids.length) return;
    const form = new FormData(event.currentTarget);
    const references = String(form.get('evidence_references')).split(/\r?\n/).map(item => item.trim()).filter(Boolean);
    if (!references.length || new Set(references).size !== references.length) { onError(new Error('Provide at least one unique completion evidence reference.')); return; }
    const values = { expected_version: stored.version, reason: String(form.get('reason')).trim(), confirmed: true, component_ids: action.component_ids, evidence_references: references, completed_kit_id: action.kind === 'rebuild' ? String(form.get('completed_kit_id')).trim() : null };
    const key = JSON.stringify(values);
    if (pending.current?.key !== key) pending.current = { key, body: { ...values, operation_id: newId('complete') } };
    setBusy(true); onBusy(true);
    try { const updated = await api.post<StoredPlan>(`/plans/${idPath(stored.plan.plan_id)}/actions/${idPath(action.action_id)}/complete`, pending.current.body); pending.current = null; await onComplete(updated); }
    catch (error) { onError(error); if (isConflict(error)) { await onReload().catch(onError); await refresh().catch(onError); } }
    finally { setBusy(false); onBusy(false); }
  }
  return <details className="completion"><summary>Confirm {action.kind === 'rebuild' ? 'kit rebuild' : action.kind} completion</summary>{!can(actor, 'executor') && <Notice>A human executor role is required to complete this action.</Notice>}<form onSubmit={complete}><fieldset disabled={busy || operationBusy || !can(actor, 'executor')}><p>Collect the reserved identities below and confirm the physical work. This records completion and consumes their inventory allocation; it does not process a payment or certify hidden function or safety.</p>{action.component_ids.map(id => <label className="checkbox" key={id}><input type="checkbox" checked={checked.includes(id)} onChange={event => setChecked(ids => event.target.checked ? [...ids, id] : ids.filter(item => item !== id))} />I checked physical component {id}</label>)}{action.kind === 'rebuild' && <Field label="Completed kit ID"><input name="completed_kit_id" required maxLength={128} pattern={'[A-Za-z0-9_\\-]+'} placeholder="kit-001" /></Field>}<Field label="Completion evidence references" hint="One reference per line. Existing asset: IDs must belong to this action. Other references remain metadata only; no external URL is fetched."><textarea name="evidence_references" required rows={2} maxLength={8192} placeholder="Internal work-order or inspection record reference" /></Field><p className="muted">Do not add new component images after reservation. New intake evidence invalidates the plan; cancel and replan before changing it.</p><Field label="Completion reason"><textarea name="reason" required maxLength={2048} rows={2} /></Field><label className="checkbox"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm this physical action is complete.</label><button className="primary" disabled={busy || operationBusy || !can(actor, 'executor') || !confirmed || checked.length !== action.component_ids.length}>Record completion</button></fieldset></form></details>;
}

export function Stock({ data, onReview, onOpenPlan }: WorkspaceProps & { onReview: (id: string) => void; onOpenPlan: (id: string) => void }) {
  return <><div className="page-intro"><h2>Trace every object through recovery.</h2><p>Availability, reservations, and consumed lineage are authoritative server records.</p></div><Section title="Physical inventory">{data.inventory.items.length ? <div className="table-scroll"><table><thead><tr><th>Component / source return</th><th>Verified identity</th><th>Evidence</th><th>Availability</th><th /></tr></thead><tbody>{data.inventory.items.map(entry => <tr key={entry.item.component.physical_component_id}><td><strong>{entry.item.component.physical_component_id}</strong><small>{entry.item.component.source_return_id}</small></td><td>{entry.item.evidence.verification ? `${entry.item.evidence.verification.identity.component_type_id} · ${entry.item.evidence.verification.identity.revision}` : 'Unverified'}<small>{entry.item.evidence.verification?.visible_condition ?? 'Condition unknown'}</small></td><td><Badge value={entry.item.evidence.state} /><small>Version {entry.item.evidence.version}</small></td><td><Badge value={entry.availability} />{entry.plan_id && <button className="text-button" onClick={() => onOpenPlan(entry.plan_id!)}>Reservation / disposition</button>}</td><td><button className="text-button" onClick={() => onReview(entry.item.component.physical_component_id)}>Review component</button></td></tr>)}</tbody></table></div> : <Empty>No physical components registered.</Empty>}</Section><Section title="Completed kits & lineage">{data.inventory.completed_kits.length ? <div className="kit-grid">{data.inventory.completed_kits.map(kit => <article className="action-card" key={kit.completed_kit_id}><Badge value="completed" /><h3>{kit.completed_kit_id}</h3><p>{kit.configuration_id}</p><ul>{kit.component_ids.map(id => <li key={id}><code>{id}</code></li>)}</ul><small>Confirmed by {kit.operator_id} · {dateTime(kit.completed_at)}</small><details><summary>Completion evidence</summary>{kit.evidence_references.map(reference => <code key={reference}>{reference}</code>)}</details><button className="text-button" onClick={() => onOpenPlan(kit.plan_id)}>Open recovery audit →</button></article>)}</div> : <Empty>No kits have completed operator confirmation yet.</Empty>}</Section></>;
}
