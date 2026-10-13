import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { idPath, newId } from './api';
import type { WorkspaceProps } from './workspace';
import type { CurrentEvidence, EvidenceHistory, ImageAsset, UploadResult } from './types';
import { InferencePanel } from './inference';
import { AssetPreview, Badge, Empty, Field, Notice, Section, can, dateTime, isConflict } from './ui';

const inputId = { required: true, maxLength: 128, pattern: '[A-Za-z0-9_\\-]+', title: 'Use letters, numbers, hyphens, and underscores.' };

export function Intake({ api, actor, data, refresh, onError, onMessage, onReview }: WorkspaceProps & { onReview: (id: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [batchId, setBatchId] = useState('');
  const [returnId, setReturnId] = useState('');
  const [familyId, setFamilyId] = useState(data.catalog.families[0]?.family_id ?? '');
  const [componentId, setComponentId] = useState('');
  const [assets, setAssets] = useState<ImageAsset[]>([]);
  const selected = data.inventory.items.find(entry => entry.item.component.physical_component_id === componentId);
  const locked = selected?.availability === 'reserved' || selected?.availability === 'consumed';
  async function submit(event: FormEvent<HTMLFormElement>, path: string, build: (form: FormData) => unknown, complete?: (form: FormData) => void) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true);
    try { await api.post(path, build(form)); complete?.(form); await refresh(); onMessage('Intake record registered. Identity still requires evidence and review.'); }
    catch (error) { onError(error); } finally { setBusy(false); }
  }
  useEffect(() => {
    let current = true; setAssets([]);
    if (componentId) void api.get<ImageAsset[]>(`/components/${idPath(componentId)}/images`).then(items => { if (current) setAssets(items); }).catch(error => { if (current) onError(error); });
    return () => { current = false; };
  }, [componentId, api]);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected || locked) return;
    const form = event.currentTarget; const files = (form.elements.namedItem('images') as HTMLInputElement).files;
    if (!files?.length) return; setBusy(true);
    try {
      let duplicates = 0;
      for (const file of Array.from(files)) {
        if (file.size > 10 * 1024 * 1024) throw new Error('Each image must be at most 10 MiB.');
        const result = await api.post<UploadResult>(`/components/${idPath(componentId)}/images?return_id=${idPath(selected.item.component.source_return_id)}`, file);
        if (result.duplicate) duplicates++;
      }
      setAssets(await api.get<ImageAsset[]>(`/components/${idPath(componentId)}/images`)); await refresh(); form.reset();
      onMessage(`Image evidence saved for ${componentId}. ${duplicates ? `${duplicates} duplicate upload(s) reused existing evidence. ` : ''}No additional physical stock was created.`);
    } catch (error) { onError(error); await refresh().catch(onError); }
    finally { setBusy(false); }
  }
  const disabled = !can(actor, 'intake') || busy;
  return <>
    <div className="page-intro"><h2>One object. One identity.</h2><p>Register the physical return first, then add as many views as you need to support review.</p></div>
    {!can(actor, 'intake') && <Notice>Intake role required to register returns or upload images.</Notice>}
    <div className="intake-grid">
      <Section eyebrow="STEP 01" title="Register batch"><form onSubmit={event => submit(event, '/batches', form => ({ batch_id: form.get('batch_id'), received_at: new Date().toISOString() }), form => setBatchId(String(form.get('batch_id'))))}><Field label="Batch ID"><input name="batch_id" placeholder="batch-2026-001" {...inputId} /></Field><button className="secondary" disabled={disabled}>Register batch</button></form></Section>
      <Section eyebrow="STEP 02" title="Register return"><form onSubmit={event => submit(event, '/returns', form => ({ return_id: form.get('return_id'), batch_id: form.get('batch_id'), product_family_id: familyId, declared_configuration_id: form.get('configuration_id') || null, received_at: new Date().toISOString() }), form => setReturnId(String(form.get('return_id'))))}>
        <Field label="Source batch"><select name="batch_id" value={batchId} onChange={event => setBatchId(event.target.value)} required><option value="">Select batch</option>{data.batches.map(batch => <option key={batch.batch_id}>{batch.batch_id}</option>)}</select></Field>
        <Field label="Return ID"><input name="return_id" placeholder="return-001" {...inputId} /></Field><Field label="Product family"><select value={familyId} onChange={event => setFamilyId(event.target.value)} required>{data.catalog.families.map(family => <option key={family.family_id} value={family.family_id}>{family.name}</option>)}</select></Field>
        <Field label="Declared configuration"><select name="configuration_id"><option value="">Unknown / not declared</option>{data.catalog.configurations.filter(config => config.family_id === familyId).map(config => <option key={config.configuration_id}>{config.configuration_id}</option>)}</select></Field><button className="secondary" disabled={disabled}>Register return</button>
      </form></Section>
      <Section eyebrow="STEP 03" title="Register component"><form onSubmit={event => submit(event, '/components', form => ({ physical_component_id: form.get('physical_component_id'), source_return_id: form.get('source_return_id'), registered_at: new Date().toISOString() }), form => setComponentId(String(form.get('physical_component_id'))))}>
        <Field label="Source return"><select name="source_return_id" value={returnId} onChange={event => setReturnId(event.target.value)} required><option value="">Select return</option>{data.returns.map(record => <option key={record.return_id}>{record.return_id}</option>)}</select></Field><Field label="Physical component ID" hint="Attach this unique ID to the physical object. A new view is not a new component."><input name="physical_component_id" placeholder="component-001" {...inputId} /></Field><button className="secondary" disabled={disabled}>Register component</button>
      </form></Section>
    </div>
    <Section eyebrow="IMAGE EVIDENCE" title="Add another view" aside={componentId && <button className="text-button" onClick={() => onReview(componentId)}>Open component review →</button>}>
      <form onSubmit={upload}><div className="form-grid"><Field label="Component to photograph"><select value={componentId} disabled={busy} onChange={event => setComponentId(event.target.value)} required><option value="">Select physical component</option>{data.inventory.items.map(entry => <option key={entry.item.component.physical_component_id} value={entry.item.component.physical_component_id}>{entry.item.component.physical_component_id} · {entry.availability}</option>)}</select></Field><Field label="Component images" hint="JPEG, PNG, or WebP · 10 MiB each · 16 million pixels · static images only"><input name="images" type="file" accept="image/jpeg,image/png,image/webp" multiple required disabled={disabled || locked || !selected} /></Field></div>
        {locked ? <Notice>This component is {selected!.availability}. Image intake is disabled. A new view changes the evidence version; cancel and replan before changing reserved evidence. These uploads are not a completion-photo workflow.</Notice> : <p className="muted">Adding a view after verification requires a fresh human review. The server checks format, content, and component ownership.</p>}
        <button className="primary" disabled={disabled || locked || !selected}>Upload images</button>
      </form><div className="asset-grid">{assets.map(asset => <AssetPreview key={asset.asset_id} asset={asset} api={api} />)}</div>
    </Section>
  </>;
}

export function Review({ api, actor, data, refresh, onError, onMessage, componentId, onSelect }: WorkspaceProps & { componentId: string; onSelect: (id: string) => void }) {
  const [history, setHistory] = useState<EvidenceHistory | null>(null);
  const [assets, setAssets] = useState<ImageAsset[]>([]);
  const [typeId, setTypeId] = useState('');
  const [revision, setRevision] = useState('');
  const [busy, setBusy] = useState(false);
  const [reviewReason, setReviewReason] = useState('');
  const [compatibility, setCompatibility] = useState<{ compatible: boolean; reasons: string[] } | null>(null);
  const pending = useRef<{ key: string; body: unknown } | null>(null);
  const scope = useRef(0);
  const readSequence = useRef(0);
  const latestHistory = useRef<EvidenceHistory | null>(null);
  const entry = data.inventory.items.find(item => item.item.component.physical_component_id === componentId);
  const locked = entry?.availability === 'reserved' || entry?.availability === 'consumed';
  const returnRecord = data.returns.find(record => record.return_id === entry?.item.component.source_return_id);
  const types = data.catalog.component_types.filter(type => type.family_id === returnRecord?.product_family_id);
  const applyHistory = (next: EvidenceHistory, nextAssets: ImageAsset[]) => {
    if (next.component.physical_component_id !== componentId || next.current.version < (latestHistory.current?.current.version ?? 0)) return;
    if (!latestHistory.current || next.current.verification?.verification_id !== latestHistory.current.current.verification?.verification_id) {
      setTypeId(next.current.verification?.identity.component_type_id ?? '');
      setRevision(next.current.verification?.identity.revision ?? '');
    }
    latestHistory.current = next; setHistory(next); setAssets(nextAssets); setCompatibility(null);
  };
  const load = async () => {
    const current = scope.current; const sequence = ++readSequence.current;
    const [nextHistory, nextAssets] = await Promise.all([api.get<EvidenceHistory>(`/components/${idPath(componentId)}/history`), api.get<ImageAsset[]>(`/components/${idPath(componentId)}/images`)]);
    if (scope.current === current && readSequence.current === sequence) applyHistory(nextHistory, nextAssets);
  };
  useEffect(() => {
    ++scope.current; latestHistory.current = null; setHistory(null); setAssets([]); setCompatibility(null); setTypeId(''); setRevision(''); pending.current = null;
    return () => { ++scope.current; };
  }, [componentId, api]);
  useEffect(() => {
    const current = scope.current;
    if (componentId) void load().catch(error => { if (scope.current === current) onError(error); });
  }, [componentId, api, entry?.item.evidence.version]);
  const updated = async () => {
    const current = scope.current; await refresh();
    if (scope.current === current) await load();
  };
  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!history || locked) return;
    const form = new FormData(event.currentTarget);
    const observations = form.getAll('observation_id').map(String);
    if (!observations.length) { onError(new Error('Select at least one observation supporting this verification.')); return; }
    const values = { physical_component_id: componentId, identity: { component_type_id: typeId, revision }, evidence_observation_ids: observations, visible_condition: form.get('condition'), reason: form.get('reason'), supersedes_verification_id: history.current.verification?.verification_id ?? null };
    const key = JSON.stringify([values, history.current.version]);
    if (pending.current?.key !== key) pending.current = { key, body: { expected_version: history.current.version, verification: { ...values, verification_id: newId('verification'), verified_at: new Date().toISOString() } } };
    const current = scope.current; setBusy(true);
    try { await api.post<CurrentEvidence>(`/components/${idPath(componentId)}/verification`, pending.current.body); if (scope.current !== current) return; pending.current = null; await updated(); if (scope.current === current) onMessage('Human verification recorded with its evidence links and actor identity.'); }
    catch (error) { if (scope.current !== current) return; onError(error); if (isConflict(error)) await updated().catch(onError); }
    finally { if (scope.current === current) setBusy(false); }
  }
  return <>
    <div className="page-intro"><h2>Evidence into an accountable decision.</h2><p>Inspect the views, select the supporting observations, and record exactly what is visible.</p></div>
    <Section title="Choose a physical component"><Field label="Component to review"><select value={componentId} disabled={busy} onChange={event => { setReviewReason(''); onSelect(event.target.value); }}><option value="">Select component</option>{data.inventory.items.map(entry => <option key={entry.item.component.physical_component_id} value={entry.item.component.physical_component_id}>{entry.item.component.physical_component_id} · {entry.item.evidence.state} · {entry.availability}</option>)}</select></Field></Section>
    {!history ? <Empty>{componentId ? 'Loading evidence…' : 'Select a component to inspect its evidence and review history.'}</Empty> : <>
      <div className="context-line"><code>{componentId}</code><Badge value={history.current.state} /><Badge value={entry?.availability ?? 'unknown'} /><span>Evidence version {history.current.version} · Source return {history.component.source_return_id}</span></div>
      {history.current.unresolved_reasons.length > 0 && <Notice>{history.current.unresolved_reasons.join(' · ')}</Notice>}
      <InferencePanel api={api} actor={actor} componentId={componentId} history={history} assets={assets} locked={!!locked || busy} catalog={{ ...data.catalog, component_types: types }} onUpdated={updated} onProposal={candidate => { setTypeId(candidate.component_type_id); setRevision(candidate.revision ?? ''); pending.current = null; }} />
      <div className="review-grid"><Section title="Views & provenance" aside={<span>{assets.length} managed images</span>}>{assets.length ? <div className="asset-grid">{assets.map(asset => <AssetPreview key={asset.asset_id} api={api} asset={asset} />)}</div> : <Empty>No managed images. Existing external observations are references only; ReKit does not fetch them.</Empty>}
        <details className="history"><summary>Evidence history · {history.events.length} events</summary>{history.events.map(event => <article key={event.sequence}><Badge value={event.kind} /><strong>{event.event_id}</strong><small>{dateTime(event.recorded_at)}</small><pre>{JSON.stringify(event.payload, null, 2)}</pre></article>)}</details>
      </Section><Section title={history.current.verification ? 'Correct / re-verify' : 'Human verification'}>
        {locked && <Notice>Review changes are disabled for {entry!.availability} stock. Cancel a reservation and replan before changing identity or evidence.</Notice>}
        {!can(actor, 'reviewer') && <Notice>A human reviewer role is required to verify or correct identity.</Notice>}
        <form onSubmit={verify} key={`${componentId}-${history.current.version}`}><fieldset disabled={busy || locked || !can(actor, 'reviewer')}>
          <Field label="Component type"><select value={typeId} onChange={event => { setTypeId(event.target.value); setRevision(''); }} required><option value="">Select catalog type</option>{types.map(type => <option key={type.component_type_id} value={type.component_type_id}>{type.name} ({type.component_type_id})</option>)}</select></Field>
          <Field label="Revision"><select name="revision" value={revision} onChange={event => setRevision(event.target.value)} required><option value="">Select revision</option>{data.catalog.revisions.filter(revision => revision.component_type_id === typeId).map(revision => <option key={revision.revision}>{revision.revision}</option>)}</select></Field>
          <Field label="Visible condition"><select name="condition" defaultValue={history.current.verification?.visible_condition ?? 'unknown'}><option value="unknown">Unknown — held</option><option value="acceptable">Acceptable visible condition</option><option value="damaged">Visible damage</option></select></Field>
          <div className="field"><span>Supporting observations</span>{history.events.filter(event => event.kind === 'observation').map(event => <label className="checkbox" key={event.event_id}><input type="checkbox" name="observation_id" value={event.event_id} defaultChecked={history.current.verification?.evidence_observation_ids.includes(event.event_id)} /><span><strong>{event.event_id}</strong><small>{String(event.payload.evidence_reference)}</small></span></label>)}</div>
          {history.current.verification && <p className="muted">This explicitly supersedes <code>{history.current.verification.verification_id}</code>. Previous assertions remain in history.</p>}
          <Field label="Review reason"><textarea name="reason" required value={reviewReason} onChange={event => setReviewReason(event.target.value)} maxLength={2048} rows={3} placeholder="Describe the visible markings, revision, condition, and any correction." /></Field><p className="muted">AI hypotheses are unverified. Confirm or correct identity from the actual evidence. Visual inspection cannot establish hidden functionality or safety.</p><button className="primary" type="submit">{history.current.verification ? 'Record correction' : 'Verify component'}</button>
        </fieldset></form>
        <form className="separated" onSubmit={event => { event.preventDefault(); const config = String(new FormData(event.currentTarget).get('configuration')); const current = scope.current; const evidenceVersion = history.current.version; setBusy(true); void api.get<{ compatible: boolean; reasons: string[] }>(`/components/${idPath(componentId)}/compatibility?configuration_id=${idPath(config)}`).then(result => { if (scope.current === current && latestHistory.current?.current.version === evidenceVersion) setCompatibility(result); }).catch(error => { if (scope.current === current) onError(error); }).finally(() => { if (scope.current === current) setBusy(false); }); }}><Field label="Check against configuration"><select name="configuration" required disabled={busy}>{data.catalog.configurations.map(config => <option key={config.configuration_id}>{config.configuration_id}</option>)}</select></Field><button className="secondary" disabled={busy}>Check compatibility</button></form>{compatibility && <Notice danger={!compatibility.compatible}>{compatibility.compatible ? 'Compatible under the approved policy. Availability is checked separately.' : 'Compatibility not established.'} {compatibility.reasons.join(' ')}</Notice>}
      </Section></div>
    </>}
  </>;
}
