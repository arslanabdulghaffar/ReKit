import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiClient, ApiError, idPath, newId } from './api';
import type { Actor, Catalog, CurrentEvidence, EvidenceHistory, IdentityCandidate, ImageAsset, InferenceRun, InferenceStatus, UploadResult } from './types';
import { AssetPreview, Badge, Field, Notice, Section, can, dateTime, errorText, isConflict } from './ui';
import { focusEvidence } from './evidence-history';

export interface InferencePanelProps {
  api: ApiClient; actor: Actor; componentId: string; history: EvidenceHistory;
  assets: ImageAsset[]; locked: boolean; catalog: Catalog;
  onUpdated: () => Promise<void>; onProposal: (candidate: IdentityCandidate) => void;
}
type AnalyzeBody = { request_id: string; asset_ids: string[]; expected_version: number };

const revisionLabel = (provider: string | null | undefined, revision: string | null | undefined) =>
  provider === 'amd-tokenfactory' ? 'Weight/processor revision not attested by shared service'
    : `${provider === 'openai-remote' ? 'Configured revision' : 'Revision'} ${revision ?? 'unknown'}`;

export function InferencePanel({ api, actor, componentId, history, assets, locked, catalog, onUpdated, onProposal }: InferencePanelProps) {
  const [status, setStatus] = useState<InferenceStatus | null>(null);
  const [runs, setRuns] = useState<InferenceRun[]>([]);
  const [runId, setRunId] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [idlePending, setIdlePending] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [retry, setRetry] = useState<AnalyzeBody | null>(null);
  const [reason, setReason] = useState('');
  const rejection = useRef<{ key: string; body: { rejection_id: string; expected_version: number; reason: string } } | null>(null);
  const scope = useRef(0);
  const sourceDetails = useRef<HTMLDetailsElement>(null);
  const updated = useRef(onUpdated); updated.current = onUpdated;
  const run = runs.find(item => item.start.run_id === runId) ?? null;
  const tokenFactoryStatus = status?.provider === 'amd-tokenfactory';
  const tokenFactoryRun = run?.start.configuration.provider === 'amd-tokenfactory';
  const remoteStatus = status?.provider === 'openai-remote' || tokenFactoryStatus;
  const remoteRun = run?.start.configuration.provider === 'openai-remote' || tokenFactoryRun;
  const reviewer = can(actor, 'reviewer');
  const outcome = run?.outcome;
  const historical = !!run && (!!outcome?.stale || history.current.version > (outcome?.evidence_version_after ?? run.start.evidence_version));
  const pending = !!run && !outcome && !idlePending;
  const rejected = run ? history.events.filter(event => event.kind === 'uncertainty' && String(event.payload.reason ?? '').startsWith(`Rejected unverified AI inspection ${run.start.run_id} at evidence version `)) : [];
  const inputReady = !!outcome && history.current.version === outcome.evidence_version_after;
  const available = assets.filter(asset => asset.availability === 'available');
  const sourcePath = `/components/${idPath(componentId)}/inference`;

  const saveRun = (next: InferenceRun) => {
    if (next.start.physical_component_id !== componentId) throw new Error('The inference record belongs to another physical component.');
    setRuns(items => [next, ...items.filter(item => item.start.run_id !== next.start.run_id)]);
    setRunId(next.start.run_id);
  };

  useEffect(() => {
    const current = ++scope.current;
    setStatus(null); setRuns([]); setRunId(''); setSelected([]); setError(''); setMessage('');
    setRetry(null); setReason(''); setIdlePending(false); setLoading(true); setBusy(false); rejection.current = null;
    void (async () => {
      try {
        const nextStatus = await api.get<InferenceStatus>('/inference/status');
        if (scope.current !== current) return;
        setStatus(nextStatus);
        if (nextStatus.provider !== null) {
          const nextRuns = await api.get<InferenceRun[]>(sourcePath);
          if (scope.current !== current) return;
          if (nextRuns.some(item => item.start.physical_component_id !== componentId)) throw new Error('Inference history contains a different physical component.');
          let completedDuringRead = false;
          if (nextRuns[0] && !nextRuns[0].outcome && !nextStatus.busy) {
            nextRuns[0] = await api.get<InferenceRun>(`/inference/${idPath(nextRuns[0].start.run_id)}`);
            if (scope.current !== current) return;
            if (nextRuns[0].start.physical_component_id !== componentId) throw new Error('The inference record belongs to another physical component.');
            completedDuringRead = !!nextRuns[0].outcome;
          }
          setRuns(nextRuns); setRunId(nextRuns[0]?.start.run_id ?? '');
          setIdlePending(!!nextRuns[0] && !nextRuns[0].outcome && !nextStatus.busy);
          if (completedDuringRead) await updated.current();
        }
      } catch (failure) { if (scope.current === current) setError(errorText(failure)); }
      finally { if (scope.current === current) setLoading(false); }
    })();
    return () => { ++scope.current; };
  }, [api, componentId, sourcePath]);

  useEffect(() => {
    const ids = new Set(available.map(asset => asset.asset_id));
    setSelected(items => items.filter(id => ids.has(id)));
  }, [assets]);

  useEffect(() => {
    if (!pending && !status?.busy) return;
    const current = scope.current;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const active = () => !cancelled && current === scope.current;
    const poll = async () => {
      try {
        const [nextStatus, polledRun] = await Promise.all([
          api.get<InferenceStatus>('/inference/status'),
          pending && run ? api.get<InferenceRun>(`/inference/${idPath(run.start.run_id)}`) : Promise.resolve(null),
        ]);
        if (!active()) return;
        let nextRun = polledRun;
        if (nextRun && !nextRun.outcome && !nextStatus.busy) {
          nextRun = await api.get<InferenceRun>(`/inference/${idPath(nextRun.start.run_id)}`);
          if (!active()) return;
        }
        setStatus(nextStatus);
        if (nextRun) {
          saveRun(nextRun); setIdlePending(!nextRun.outcome && !nextStatus.busy);
          if (nextRun.outcome) await updated.current();
        }
      } catch (failure) { if (active()) setError(errorText(failure)); }
      if (active()) timer = setTimeout(() => { void poll(); }, 1500);
    };
    timer = setTimeout(() => { void poll(); }, 1500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [api, componentId, run?.start.run_id, pending, status?.busy]);

  async function analyze(body?: AnalyzeBody) {
    if (busy || locked || !reviewer) return;
    const current = scope.current;
    const request = body ?? { request_id: newId('inspection'), asset_ids: selected, expected_version: history.current.version };
    setBusy(true); setError(''); setMessage('');
    try {
      const nextRun = await api.post<InferenceRun>(sourcePath, request);
      if (scope.current !== current) return;
      saveRun(nextRun); setRetry(null); setIdlePending(false); setReason(''); rejection.current = null;
      if (nextRun.outcome) await updated.current();
      if (scope.current !== current) return;
      const nextStatus = await api.get<InferenceStatus>('/inference/status');
      if (scope.current !== current) return;
      setStatus(nextStatus);
      if (!nextRun.outcome && !nextStatus.busy) {
        // A fast run may finish between POST admission and the status request.
        // Confirm the stored outcome before calling a pending record orphaned.
        const latest = await api.get<InferenceRun>(`/inference/${idPath(nextRun.start.run_id)}`);
        if (scope.current !== current) return;
        saveRun(latest); setIdlePending(!latest.outcome);
        if (latest.outcome) await updated.current();
      }
    } catch (failure) {
      if (scope.current !== current) return;
      setError(errorText(failure));
      setRetry(failure instanceof ApiError && failure.status === 0 ? request : null);
      if (isConflict(failure)) await updated.current().catch(problem => { if (scope.current === current) setError(errorText(problem)); });
    } finally { if (scope.current === current) setBusy(false); }
  }

  async function reject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!run || !outcome || historical || !inputReady || locked || busy || !reviewer) return;
    const current = scope.current;
    const key = JSON.stringify([run.start.run_id, history.current.version, reason]);
    if (rejection.current?.key !== key) rejection.current = { key, body: { rejection_id: newId('rejection'), expected_version: history.current.version, reason } };
    setBusy(true); setError(''); setMessage('');
    try {
      await api.post<CurrentEvidence>(`/inference/${idPath(run.start.run_id)}/reject`, rejection.current.body);
      if (scope.current !== current) return;
      await updated.current();
      if (scope.current === current) { setMessage('Rejection recorded. The original model output remains in history. Review the current evidence before making a new human decision.'); setReason(''); rejection.current = null; }
    } catch (failure) {
      if (scope.current !== current) return;
      setError(errorText(failure));
      if (isConflict(failure)) await updated.current().catch(problem => { if (scope.current === current) setError(errorText(problem)); });
    } finally { if (scope.current === current) setBusy(false); }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || locked || !can(actor, 'intake')) return;
    const form = event.currentTarget;
    const files = Array.from((form.elements.namedItem('additional_images') as HTMLInputElement).files ?? []);
    if (!files.length) return;
    const current = scope.current; setBusy(true); setError(''); setMessage('');
    try {
      if (files.some(file => file.size > 10 * 1024 * 1024)) throw new Error('Each image must be at most 10 MiB.');
      let duplicates = 0;
      for (const file of files) {
        if (scope.current !== current) return;
        const result = await api.post<UploadResult>(`/components/${idPath(componentId)}/images?return_id=${idPath(history.component.source_return_id)}`, file);
        if (result.duplicate) duplicates++;
      }
      if (scope.current !== current) return;
      await updated.current();
      if (scope.current === current) { form.reset(); setMessage(`Additional views saved for ${componentId}. ${duplicates ? `${duplicates} duplicate upload(s) reused existing evidence. ` : ''}No new physical stock was created. Select the new view to analyze again.`); }
    } catch (failure) {
      if (scope.current !== current) return;
      setError(errorText(failure)); await updated.current().catch(problem => { if (scope.current === current) setError(errorText(problem)); });
    } finally { if (scope.current === current) setBusy(false); }
  }

  const imageLabel = (assetId: string) => {
    const index = assets.findIndex(asset => asset.asset_id === assetId);
    return index >= 0 ? `Image ${index + 1}` : 'Unavailable view';
  };
  const runAsset = (input: InferenceRun['start']['inputs'][number]) => assets.find(asset => asset.asset_id === input.asset_id
    && asset.sha256 === input.sha256 && asset.observation_id === input.observation_id
    && asset.physical_component_id === run?.start.physical_component_id && asset.return_id === run?.start.source_return_id);
  const runImageId = (index: number) => `run-source-${run?.start.run_id}-${index}`;
  const sources = (indices: number[]) => <small className="inference-sources">{indices.map((index, position) => {
    const input = run?.start.inputs[index - 1];
    return <span key={`${index}-${position}`}>{position > 0 && ' · '}{input && runAsset(input)
      ? <a href={`#${runImageId(index)}`} onClick={event => { event.preventDefault(); if (sourceDetails.current) sourceDetails.current.open = true; focusEvidence(runImageId(index)); }}>{`Run image ${index}: ${imageLabel(input.asset_id)} in the gallery`}</a>
      : `Run image ${index}: original source unavailable or mismatched`}</span>;
  })}</small>;
  const canAnalyze = reviewer && !locked && !busy && !loading && !status?.busy && !pending && !!status?.provider && selected.length >= 1 && selected.length <= 2 && !retry;
  return <Section eyebrow="2 · UNVERIFIED AI SUGGESTIONS" title="AI-assisted inspection" aside={<Badge value={loading ? 'checking' : status?.status ?? 'unknown'} />}>
    <p>AI output is unverified. Compare each claim with its images and uncertainty. Only explicit human verification can establish an eligible identity.</p>
    {status?.model_repository && <div className="context-line"><strong>{status.model_repository}</strong><span>{status.provider} · {status.device}</span><code>{revisionLabel(status.provider, status.model_revision)}</code></div>}
    {(tokenFactoryStatus || tokenFactoryRun) && <Notice>AMD TokenFactory is a shared remote service. Weight and processor revisions are not attested by the shared service. Its GPU model and server runtime remain unverified.</Notice>}
    {(remoteStatus || remoteRun) && <Notice>Remote responses are checked for the configured model ID. The response does not verify deployed weights, runtime, or AMD hardware.</Notice>}
    {status?.status === 'unavailable' && <Notice>AI image analysis is unavailable. Continue manual inspection and human verification below; no AI fallback is used.</Notice>}
    {status?.status === 'unavailable' && status.provider !== null && <Notice>A provider is configured. You may select images and choose Analyze images to attempt inspection again. The request can still fail; no result is assumed.</Notice>}
    {!reviewer && <Notice>A human reviewer role is required to analyze images, review proposals, or reject them.</Notice>}
    {locked && <Notice>AI and image changes are disabled while this component is reserved, consumed, or another review action is being saved. Cancel and replan before changing reserved evidence.</Notice>}
    {error && <Notice danger>{error}</Notice>}{message && <Notice>{message}</Notice>}
    <fieldset disabled={busy || locked || !reviewer || !!retry || pending}>
      <legend>Select one or two existing views</legend>
      {available.length ? available.map(asset => <label className="checkbox" key={asset.asset_id}>
        <input type="checkbox" aria-label={`Analyze image ${asset.asset_id}`} checked={selected.includes(asset.asset_id)} disabled={selected.length >= 2 && !selected.includes(asset.asset_id)} onChange={event => setSelected(items => event.target.checked ? [...items, asset.asset_id] : items.filter(id => id !== asset.asset_id))} />
        <span><strong>{imageLabel(asset.asset_id)}</strong><small>{asset.width} × {asset.height} · Uploaded {dateTime(asset.received_at)}</small></span>
      </label>) : <p className="muted">Upload managed image evidence for this physical component to begin.</p>}
    </fieldset>
    <p className="muted">{selected.length ? `Selected order: ${selected.map(imageLabel).join(' → ')}. ` : ''}Model references follow the selected order, which can differ from the gallery. Each saved run records its own image mapping.</p>
    <div className="inference-controls"><button className="primary" disabled={!canAnalyze} onClick={() => { void analyze(); }}>Analyze images</button>
      {retry && <button className="secondary" disabled={busy || locked || !reviewer} onClick={() => { void analyze(retry); }}>Retry same request</button>}
      <button className="text-button" disabled={busy || loading} onClick={() => { const current = scope.current; void api.get<InferenceStatus>('/inference/status').then(next => { if (scope.current === current) setStatus(next); }).catch(failure => { if (scope.current === current) setError(errorText(failure)); }); }}>Refresh analysis status</button>
    </div>
    {retry && <Notice>The server response was lost. Retry the same request to recover its recorded result without starting a duplicate. The original images and evidence version are retained.</Notice>}
    {(pending || status?.busy) && <Notice>{status?.status === 'loading' ? 'Loading the image-analysis model.' : pending ? 'Analyzing the selected images.' : 'Image analysis is busy with another request.'} Results remain unverified. You can inspect the original views while waiting; new images or a human decision will make an earlier result historical.</Notice>}
    {idlePending && <Notice>This pending record has no active worker. Its result is unknown, not a success. You may start a new request when the provider is available.</Notice>}
    {runs.length > 1 && <Field label="Inspection run"><select value={runId} disabled={busy} onChange={event => { setRunId(event.target.value); setReason(''); setIdlePending(!runs.find(item => item.start.run_id === event.target.value)?.outcome && !status?.busy); }}>{runs.map(item => <option key={item.start.run_id} value={item.start.run_id}>{dateTime(item.start.started_at)} · {item.outcome?.status ?? 'pending'} · {item.start.run_id}</option>)}</select></Field>}
    {run && <div className="inference-result">
      <div className="context-line"><Badge value={outcome?.status ?? 'pending'} /><Badge value="unverified" /><code>{run.start.run_id}</code><span>Input evidence version {run.start.evidence_version}</span></div>
      <p className="muted">Run model: {run.start.configuration.model_repository} · {run.start.configuration.provider} · {run.start.configuration.device} · {tokenFactoryRun ? <span>{revisionLabel(run.start.configuration.provider, run.start.configuration.model_revision)}</span> : <>{remoteRun ? 'Configured revision' : 'Revision'} <code>{run.start.configuration.model_revision}</code></>}</p>
      {historical && <Notice danger>Stale or historical inspection. {outcome?.stale_reason ?? 'Newer component evidence exists.'} This output cannot prefill or replace the current human decision.</Notice>}
      {rejected.map(event => <Notice key={event.event_id}>{String(event.payload.reason)}</Notice>)}
      {outcome?.failure_reason && <Notice danger>{outcome.failure_reason} Continue manual inspection, or retry with a new request when the provider is ready.</Notice>}
      {outcome?.status === 'succeeded' && <Notice>Analysis finished. Compare the suggestions with the original views before recording a human decision.</Notice>}
      <details ref={sourceDetails}><summary>Source images & run provenance</summary><p>Run image numbers below follow this request’s recorded input order, not the current gallery order. These inputs were recorded at evidence version {run.start.evidence_version}.</p><div className="asset-grid">{run.start.inputs.map((input, index) => {
        const asset = runAsset(input);
        return <div key={input.asset_id} id={runImageId(index + 1)} tabIndex={-1} className="evidence-target" aria-label={`Original run image ${index + 1}`}><h3>Run image {index + 1} · Gallery {asset ? imageLabel(input.asset_id) : 'unavailable or mismatched'}</h3><code>{input.asset_id}</code><p><code>SHA-256 {input.sha256}</code></p><small>Observation {input.observation_id}</small>{asset ? <AssetPreview api={api} asset={asset} label={`Run image ${index + 1}`} /> : <Notice danger>The original view is unavailable or its component, return, observation, or hash does not match this run. Check the recorded source before relying on this claim.</Notice>}</div>;
      })}</div><pre>{JSON.stringify({ start: run.start, completed_at: outcome?.completed_at ?? null, metrics: outcome?.metrics ?? null, applied_event_ids: outcome?.applied_event_ids ?? [] }, null, 2)}</pre></details>
      {outcome?.output && <>
        <div className="inference-output-grid"><div><h3>Model observations</h3>{outcome.output.observations.length ? outcome.output.observations.map((observation, index) => <article className="inference-claim" key={index}><Badge value={observation.kind} /><p>{observation.text}</p>{sources(observation.image_indices)}</article>) : <p className="muted">No visual observations were returned.</p>}</div>
          <div><h3>Uncertainty & missing evidence</h3>{outcome.output.uncertainties.length ? <ul>{outcome.output.uncertainties.map((uncertainty, index) => <li key={index}>{uncertainty}</li>)}</ul> : <p className="muted">The model supplied no uncertainty statement. This does not establish confidence or correctness.</p>}
            <h3>Suggested additional photographs</h3>{outcome.output.additional_views.length ? outcome.output.additional_views.map((view, index) => <article className="inference-claim" key={index}><strong>{view.view}</strong><p>{view.reason}</p>{sources(view.image_indices)}</article>) : <p className="muted">No additional view was requested by the model.</p>}
          </div></div>
        <h3>Suggested components — unverified</h3>{!outcome.output.candidates.length && <Notice>No catalog identity was proposed by this analysis. {history.current.state === 'verified' && history.current.verification ? 'The current human-verified identity remains in effect; this analysis does not replace it.' : history.current.verification ? 'An earlier human verification remains in history, but fresh review is required. Inspect the views and resolve the missing evidence before verifying again.' : 'Identity remains unverified. Inspect the original views, add a readable close-up if needed, and record a human decision.'}</Notice>}
        {outcome.output.candidates.map((candidate, index) => {
          const known = catalog.component_types.some(type => type.component_type_id === candidate.component_type_id) && candidate.revision !== null && catalog.revisions.some(revision => revision.component_type_id === candidate.component_type_id && revision.revision === candidate.revision);
          return <article className="inference-claim" key={index}><strong>{candidate.component_type_id} · Revision {candidate.revision ?? 'unknown'}</strong><p>{candidate.reason}</p><p>Claimed revision marking: <q>{candidate.revision_marking ?? 'Not supplied'}</q></p>{sources(candidate.image_indices)}
            <button className="secondary" disabled={!known || historical || !inputReady || !!rejected.length || locked || busy || !reviewer} onClick={() => { onProposal(candidate); setMessage('Identity fields prefilled for your review. Check or correct them, choose the visible condition and supporting evidence, then explicitly verify below.'); }}>Review proposal {candidate.component_type_id} {candidate.revision ?? 'unknown revision'}</button>
            {!known && <p className="muted">No complete, known catalog identity is available to prefill. Resolve it manually.</p>}
          </article>;
        })}
        <form className="separated" onSubmit={reject}><fieldset disabled={busy || locked || !reviewer || historical || !inputReady || !!rejected.length}><Field label="Rejection reason" hint="Describe the unsupported claim. The original AI output remains auditable."><textarea required maxLength={1500} rows={2} value={reason} onChange={event => setReason(event.target.value)} /></Field><button className="danger-button">Reject unsupported proposal</button></fieldset></form>
      </>}
      {outcome?.raw_output != null && <details className="history"><summary>Original model text · unverified</summary><pre>{outcome.raw_output}</pre></details>}
    </div>}
    <form className="separated" onSubmit={upload}><Field label="Additional component images" hint="JPEG, PNG, or WebP · 10 MiB each. New views preserve this physical component ID and require fresh review."><input type="file" name="additional_images" accept="image/jpeg,image/png,image/webp" multiple required disabled={busy || locked || !can(actor, 'intake')} /></Field><button className="secondary" disabled={busy || locked || !can(actor, 'intake')}>Upload another view</button>{!can(actor, 'intake') && <p className="muted">The intake role is required to upload another view.</p>}</form>
  </Section>;
}
