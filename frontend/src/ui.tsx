import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { ApiClient, ApiError } from './api';
import type { Actor, ImageAsset, Role } from './types';

export const can = (actor: Actor, role: Role): boolean => actor.roles.includes(role) && (!['reviewer', 'approver', 'executor'].includes(role) || actor.kind === 'human');
export const money = (value: number | null, currency = 'USD'): string => value === null ? '—' : `${currency} ${(value / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export const dateTime = (value: string): string => new Date(value).toLocaleString();
export const errorText = (error: unknown): string => error instanceof Error ? error.message : 'The request failed.';
export function Badge({ value }: { value: string }) { return <span className={`badge badge-${value.toLowerCase()}`}>{value.replaceAll('_', ' ')}</span>; }
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}
export function Notice({ children, danger = false }: { children: ReactNode; danger?: boolean }) { return <div className={`notice ${danger ? 'notice-danger' : ''}`} role={danger ? 'alert' : 'status'}>{children}</div>; }
export function Empty({ children }: { children: ReactNode }) { return <div className="empty">{children}</div>; }
export function Section({ title, eyebrow, children, aside }: { title: string; eyebrow?: string; children: ReactNode; aside?: ReactNode }) {
  return <section className="panel"><div className="section-heading"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h2>{title}</h2></div>{aside}</div>{children}</section>;
}
export function AssetPreview({ asset, api, label }: { asset: ImageAsset; api: ApiClient; label?: string }) {
  const [url, setUrl] = useState<string>();
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let disposed = false; let objectUrl: string | undefined;
    setUrl(undefined); setError(''); setLoaded(false);
    if (asset.availability === 'available') {
      void api.image(`/assets/${encodeURIComponent(asset.asset_id)}/content`).then(blob => {
        if (!disposed) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); }
      }).catch(error => { if (!disposed) setError(errorText(error)); });
    }
    return () => { disposed = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [asset.asset_id, asset.availability, api]);
  return <figure className="asset-card">
    <div className="asset-image" aria-busy={asset.availability === 'available' && !loaded && !error}>{url && !error ? <img src={url} alt={label ? `${label}: evidence for ${asset.physical_component_id}` : `Evidence for ${asset.physical_component_id}`} onLoad={() => setLoaded(true)} onError={() => { setError('This image could not be displayed. Reload the component or request another view.'); setLoaded(false); }} /> : <span role={error ? 'alert' : 'status'}>{error || (asset.availability === 'available' ? 'Loading original image…' : `Image ${asset.availability}. Restore the original evidence before reviewing this view.`)}</span>}</div>
    <figcaption>{label && <strong>{label}</strong>}<Badge value={asset.availability} /><span>{asset.width} × {asset.height} · {(asset.byte_size / 1024).toFixed(1)} KiB</span><small>Uploaded by {asset.uploaded_by} · {dateTime(asset.received_at)}</small><details><summary>Integrity & provenance</summary><code>{asset.asset_id}</code><code>SHA-256 {asset.sha256}</code><code>Observation {asset.observation_id}</code><small>Physical component {asset.physical_component_id} · Source return {asset.return_id}</small></details></figcaption>
  </figure>;
}
export function parseInteger(value: FormDataEntryValue | null, name: string, optional = false): number | null {
  const text = String(value ?? '').trim();
  if (!text && optional) return null;
  if (!/^\d+$/.test(text) || Number(text) > 1_000_000_000) throw new Error(`${name} must be a whole number between 0 and 1,000,000,000.`);
  return Number(text);
}
export const isConflict = (error: unknown): boolean => error instanceof ApiError && error.status === 409;
