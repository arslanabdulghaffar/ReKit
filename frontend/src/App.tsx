import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiClient } from './api';
import type { Actor, WorkspaceData, Catalog, InventorySnapshot, ReturnBatch, ReturnRecord, PlanSummary } from './types';
import { Badge, Empty, Field, Notice, errorText } from './ui';
import { Intake, Review } from './evidence';
import { Planning, Execution, Stock } from './recovery';

type Tab = 'Intake' | 'Component review' | 'Recovery planning' | 'Execution' | 'Inventory';
const tabs: Tab[] = ['Intake', 'Component review', 'Recovery planning', 'Execution', 'Inventory'];

export default function App() {
  const [session, setSession] = useState<{ actor: Actor; api: ApiClient } | null>(null);
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [tab, setTab] = useState<Tab>('Intake');
  const [componentId, setComponentId] = useState('');
  const [planId, setPlanId] = useState('');
  const [data, setData] = useState<WorkspaceData | null>(null);
  const activeClient = useRef<ApiClient | null>(null);
  const signOut = useCallback(() => {
    activeClient.current?.clear(); activeClient.current = null;
    setSession(current => { current?.api.clear(); return null; });
    setToken(''); setData(null); setComponentId(''); setPlanId(''); setMessage(''); setError('');
  }, []);
  const refresh = useCallback(async () => {
    if (!session || !session.actor.roles.includes('viewer')) return;
    const [catalog, batches, returns, inventory, plans] = await Promise.all([
      session.api.get<Catalog>('/catalog'), session.api.get<ReturnBatch[]>('/batches'),
      session.api.get<ReturnRecord[]>('/returns'), session.api.get<InventorySnapshot>('/inventory'),
      session.api.get<PlanSummary[]>('/plans?limit=50'),
    ]);
    if (activeClient.current === session.api) setData({ catalog, batches, returns, inventory, plans });
  }, [session]);
  useEffect(() => { let active = true; void refresh().catch(error => { if (active) setError(errorText(error)); }); return () => { active = false; }; }, [refresh]);
  async function signIn(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    const api = new ApiClient(token.trim(), () => { if (activeClient.current === api) signOut(); });
    setToken('');
    try { const actor = await api.get<Actor>('/auth/me'); activeClient.current = api; setSession({ actor, api }); }
    catch (error) { api.clear(); setError(errorText(error)); }
    finally { setBusy(false); }
  }
  const onError = (error: unknown) => { if (session && activeClient.current === session.api) { setError(errorText(error)); setMessage(''); } };
  const onMessage = (message: string) => { if (session && activeClient.current === session.api) { setMessage(message); setError(''); } };
  const openPlan = (id: string) => { if (session && activeClient.current === session.api) { setPlanId(id); setTab('Execution'); } };
  const reviewComponent = (id: string) => { if (session && activeClient.current === session.api) { setComponentId(id); setTab('Component review'); } };
  if (!session) return <main className="signin">
    <div className="signin-story"><div className="brand"><span className="brand-mark">R</span>ReKit<span className="brand-dot">.</span></div><p className="eyebrow">RETURN RECOVERY WORKSPACE</p><h1>Every component.<br />A clearer next step.</h1><p>Bring incomplete returns together with traceable evidence, approved compatibility, and a recovery plan your team can act on.</p><div className="story-steps"><span>01 Capture</span><span>02 Review</span><span>03 Recover</span></div><small>Visual AI supports inspection when configured. Your team verifies components and approves recovery plans. AMD inference qualification is pending.</small></div>
    <section className="signin-card"><p className="eyebrow">AUTHORIZED OPERATORS</p><h2>Sign in to ReKit</h2><p>Use the operator token issued by your administrator. Access follows your assigned roles.</p>
      {error && <Notice danger>{error}</Notice>}<form onSubmit={signIn}><Field label="Operator token"><input type="password" autoComplete="off" spellCheck={false} value={token} onChange={event => setToken(event.target.value)} required /></Field><button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button></form><small>Your token stays in memory for this session and is cleared when you sign out or refresh the page.</small>
    </section>
  </main>;
  const props = data ? { ...session, data, refresh, onError, onMessage } : null;
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">R</span>ReKit<span className="brand-dot">.</span></div><p className="workspace-label">OPERATOR WORKSPACE</p><nav aria-label="Workspace">{tabs.map((item, index) => <button key={item} className={tab === item ? 'nav-item active' : 'nav-item'} aria-current={tab === item ? 'page' : undefined} onClick={() => { setTab(item); setError(''); setMessage(''); }}><span className="nav-number">0{index + 1}</span>{item}</button>)}</nav><div className="sidebar-note"><span className="signal-dot" /> Human review · CPU planning<p>Images provide visible evidence. They do not establish hidden function or safety.</p></div><div className="operator"><strong>{session.actor.actor_id}</strong><small>{session.actor.kind} · {session.actor.roles.join(', ')}</small><button onClick={signOut}>Sign out</button></div></aside>
    <main className="workspace"><header className="workspace-header"><div><p className="eyebrow">RECOVERY OPERATIONS</p><h1>{tab}</h1></div><button className="secondary" onClick={() => { setError(''); void refresh().then(() => onMessage('Workspace refreshed.')).catch(onError); }}>Refresh workspace</button></header>
      {error && <Notice danger>{error}</Notice>}{message && <Notice>{message}</Notice>}
      {!session.actor.roles.includes('viewer') ? <Notice>Signed in with {session.actor.roles.join(', ')} access. This workspace needs the viewer role to display catalog, evidence, and inventory context. Ask your administrator to add viewer access.</Notice> : !props ? <Empty>Loading your workspace…</Empty> : <>
        <div className="metrics"><div><small>Physical components</small><strong>{data!.inventory.items.length}</strong></div><div><small>Awaiting review</small><strong>{data!.inventory.items.filter(item => item.item.evidence.state !== 'verified' && item.availability !== 'consumed').length}</strong></div><div><small>Reserved</small><strong>{data!.inventory.items.filter(item => item.availability === 'reserved').length}</strong></div><div><small>Completed kits</small><strong>{data!.inventory.completed_kits.length}</strong></div></div>
        {data!.catalog.synthetic && <div className="context-line"><Badge value="synthetic" /> This server uses an explicitly synthetic catalog. Values entered below are scenario estimates.</div>}
        {tab === 'Intake' && <Intake {...props} onReview={reviewComponent} />}
        {tab === 'Component review' && <Review key={componentId} {...props} componentId={componentId} onSelect={setComponentId} />}
        {tab === 'Recovery planning' && <Planning {...props} onOpenPlan={openPlan} />}
        {tab === 'Execution' && <Execution key={planId} {...props} planId={planId} onSelect={setPlanId} />}
        {tab === 'Inventory' && <Stock {...props} onReview={reviewComponent} onOpenPlan={openPlan} />}
      </>}
      <footer>ReKit · Evidence before approval. Every physical component has one identity.</footer>
    </main>
  </div>;
}
