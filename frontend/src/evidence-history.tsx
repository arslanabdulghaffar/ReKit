import type { EvidenceHistory, ImageAsset, Verification } from './types';
import { Badge, Notice, dateTime } from './ui';

type HistoryEvent = EvidenceHistory['events'][number];

export const originalImageId = (assetId: string) => `original-image-${assetId}`;

export function focusEvidence(id: string): void {
  const target = document.getElementById(id);
  target?.focus();
  target?.scrollIntoView?.({ block: 'center' });
}

// Evidence versions count this component's events. SQLite event sequences span
// all components and must never be presented as component evidence versions.
export function eventVersion(history: EvidenceHistory, eventId: string): number | null {
  const index = history.events.findIndex(event => event.event_id === eventId);
  return history.current.version === history.events.length + 1 && index >= 0 ? index + 2 : null;
}

export function observationAsset(history: EvidenceHistory, event: HistoryEvent, assets: ImageAsset[]): ImageAsset | undefined {
  if (event.kind !== 'observation' || event.payload.physical_component_id !== history.component.physical_component_id
    || event.payload.source_return_id !== history.component.source_return_id) return undefined;
  const asset = assets.find(asset => asset.physical_component_id === history.component.physical_component_id
    && asset.return_id === history.component.source_return_id && event.payload.evidence_reference === `asset:${asset.asset_id}`);
  // Model observations may reference an original asset with their own event ID.
  // An original capture event ID must not contradict the explicit asset reference.
  const capture = assets.find(item => item.observation_id === event.event_id);
  return asset && (!capture || capture.asset_id === asset.asset_id) ? asset : undefined;
}

export function ObservationSource({ history, observationId, assets }: { history: EvidenceHistory; observationId: string; assets: ImageAsset[] }) {
  const event = history.events.find(event => event.kind === 'observation' && event.event_id === observationId);
  const asset = event && observationAsset(history, event, assets);
  const version = eventVersion(history, observationId);
  const label = asset ? `Image ${assets.indexOf(asset) + 1}` : 'External or unavailable evidence';
  return <div className="observation-source">
    {asset ? <a className="text-button" href={`#${originalImageId(asset.asset_id)}`} onClick={event => { event.preventDefault(); focusEvidence(originalImageId(asset.asset_id)); }}>View original {label}</a> : <span>{label}</span>}
    <small>{version === null ? 'Observation version unavailable' : `Added at evidence version ${version}`} · {observationId}{asset && asset.availability !== 'available' ? ` · Image ${asset.availability}` : ''}</small>
  </div>;
}

function recordedVerification(event: HistoryEvent | undefined, componentId: string): Verification | null {
  if (!event || event.kind !== 'verification') return null;
  const value = event.payload;
  const identity = value.identity as Record<string, unknown> | undefined;
  if (value.verification_id !== event.event_id || value.physical_component_id !== componentId || !identity
    || typeof identity.component_type_id !== 'string' || typeof identity.revision !== 'string'
    || typeof value.operator_id !== 'string' || typeof value.verified_at !== 'string'
    || typeof value.reason !== 'string' || !['unknown', 'acceptable', 'damaged'].includes(String(value.visible_condition))
    || !Array.isArray(value.evidence_observation_ids) || !value.evidence_observation_ids.every(id => typeof id === 'string')) return null;
  return value as unknown as Verification;
}

export function VerificationSummary({ history, assets }: { history: EvidenceHistory; assets: ImageAsset[] }) {
  const current = history.current.verification;
  if (!current) return null;
  const previous = recordedVerification(history.events.find(event => event.event_id === current.supersedes_verification_id), history.component.physical_component_id);
  const assertions = previous ? [previous, current] : [current];
  const fields: { label: string; value: (verification: Verification) => string }[] = [
    { label: 'Component type', value: verification => verification.identity.component_type_id },
    { label: 'Revision', value: verification => verification.identity.revision },
    { label: 'Visible condition', value: verification => verification.visible_condition },
    { label: 'Review reason', value: verification => verification.reason },
  ];
  return <article className="verification-summary" aria-label="Human verification comparison">
    <h3>{previous ? 'Human correction summary' : 'Latest human verification'}</h3>
    <p>Each assertion keeps its original evidence links. A correction supersedes an assertion; it does not rewrite its history.</p>
    {history.current.state !== 'verified' && <Notice>This is the latest recorded human assertion, not a current approval. Evidence version {history.current.version} requires fresh review.</Notice>}
    {current.supersedes_verification_id && !previous && <Notice>Superseded assertion {current.supersedes_verification_id} is unavailable in this history response. No previous values are inferred.</Notice>}
    <div className="table-scroll"><table><thead><tr><th>Review field</th>{previous && <th>Previous assertion</th>}<th>Latest assertion</th></tr></thead><tbody>
      {fields.map(field => <tr key={field.label}><th scope="row">{field.label}{previous && field.value(previous) !== field.value(current) && <> <Badge value="changed" /></>}</th>{assertions.map(assertion => <td key={assertion.verification_id}>{field.value(assertion)}</td>)}</tr>)}
      <tr><th scope="row">Recorded by</th>{assertions.map(assertion => <td key={assertion.verification_id}><strong>{assertion.operator_id}</strong><small>{dateTime(assertion.verified_at)}</small></td>)}</tr>
      <tr><th scope="row">Assertion provenance</th>{assertions.map(assertion => <td key={assertion.verification_id}><code>{assertion.verification_id}</code><small>{eventVersion(history, assertion.verification_id) === null ? 'Assertion evidence version unavailable' : `Evidence version ${eventVersion(history, assertion.verification_id)} at assertion`}</small></td>)}</tr>
      <tr><th scope="row">Supporting original evidence</th>{assertions.map(assertion => <td key={assertion.verification_id}>{assertion.evidence_observation_ids.map(id => <ObservationSource key={id} history={history} observationId={id} assets={assets} />)}</td>)}</tr>
    </tbody></table></div>
    {previous && <p className="muted">Latest assertion explicitly supersedes <code>{previous.verification_id}</code>. Current component evidence version: {history.current.version}.</p>}
  </article>;
}
