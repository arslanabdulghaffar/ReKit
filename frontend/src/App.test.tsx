import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import catalogFixture from '../../tests/fixtures/synthetic_catalog.json'
import recoveryFixture from '../../tests/fixtures/synthetic_recovery.json'
import App from './App'
import { selectNativeFiles } from './test/setup'

// Transport fixtures exercise browser interactions and HTTP contracts only. The
// backend suites independently execute real validation, SQLite, and CP-SAT.
const token = 'test-operator-token-not-a-real-provisioned-secret'
const allRoles = ['viewer', 'intake', 'reviewer', 'planner', 'approver', 'executor']
const actor = { actor_id: 'synthetic-reviewer', kind: 'human', roles: allRoles }
const clone = <T,>(value: T): T => structuredClone(value)
const firstRecord = recoveryFixture.components[0]
const componentId = firstRecord.component.physical_component_id
const history = {
  component: firstRecord.component,
  current: { physical_component_id: componentId, version: 2, state: 'unresolved', verification: null, unresolved_reasons: [] },
  events: [{ sequence: 1, event_id: firstRecord.observation.observation_id, kind: 'observation', payload: firstRecord.observation, recorded_at: firstRecord.observation.captured_at }],
}
const inventory = {
  items: [{ item: { component: firstRecord.component, evidence: history.current, eligibility: 'held' }, availability: 'held', plan_id: null, action_id: null }],
  completed_kits: [],
}
const samplePlan = {
  version: 1, state: 'proposed', completed_action_ids: [] as string[],
  plan: {
    plan_id: 'synthetic-browser-plan', input_hash: 'a'.repeat(64), status: 'OPTIMAL',
    selected_actions: [{
      action_id: 'synthetic-rebuild-action', kind: 'rebuild',
      component_ids: [componentId, recoveryFixture.components[2].component.physical_component_id],
      configuration_id: 'standard-kit', source_return_id: null, labor_minutes: 30,
      cash_recovery_cents: 8750, retained_value_cents: 0, modeled_value_cents: 8750,
      donor_opportunity_cost_cents: 800, incremental_vs_retain_cents: 7950,
      explanation: ['Synthetic browser response fixture; independent backend tests validate solver output.'],
    }],
    modeled_value_cents: 8750, cash_recovery_cents: 8750, retained_value_cents: 0, labor_minutes: 30,
    best_bound_cents: 8750, absolute_gap_cents: 0, solver_version: '9.15.6755', worker_count: 1,
    wall_time_seconds: 0.01, number_of_candidates: 3, explanations: ['Scenario estimate only.'], rejections: [], scenario_estimate: true,
    problem: {
      inventory: [0, 2].map(index => ({
        component: recoveryFixture.components[index].component,
        evidence: { physical_component_id: recoveryFixture.components[index].component.physical_component_id, version: 3, state: 'verified', verification: recoveryFixture.components[index].verification, unresolved_reasons: [] },
        eligibility: 'eligible',
      })),
      scenario: {
        ...recoveryFixture.scenario,
        components: recoveryFixture.scenario.components.filter(item => [componentId, recoveryFixture.components[2].component.physical_component_id].includes(item.physical_component_id)),
        returns: recoveryFixture.scenario.returns.filter(item => [firstRecord.component.source_return_id, recoveryFixture.components[2].component.source_return_id].includes(item.return_id)),
      }, catalog: catalogFixture,
      policy: { policy_id: 'synthetic-disposition-policy', version: '1' },
      return_contents: [0, 2].map(index => ({ return_id: recoveryFixture.components[index].component.source_return_id, component_ids: [recoveryFixture.components[index].component.physical_component_id] })),
    },
  },
}
const sampleAudit = [{
  sequence: 1, plan_id: samplePlan.plan.plan_id, operation_id: 'synthetic-proposal', operator_id: actor.actor_id,
  kind: 'proposed', plan_version: 1, reason: 'Synthetic scenario review.', recorded_at: '2026-10-13T00:00:00Z', action_id: null,
}]
const summary = {
  plan_id: samplePlan.plan.plan_id, scenario_id: recoveryFixture.scenario.scenario_id, description: recoveryFixture.scenario.description,
  currency: 'USD', version: 1, state: 'proposed', status: 'OPTIMAL', modeled_value_cents: 8750, cash_recovery_cents: 8750,
  retained_value_cents: 0, created_at: '2026-10-13T00:00:00Z',
}

type Call = { method: string; path: string; init: RequestInit }
type Responder = (call: Call) => Response | undefined | Promise<Response | undefined>
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })

function transport(responder?: Responder) {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), 'http://localhost')
    const call = { method: init.method ?? 'GET', path: url.pathname + url.search, init }
    calls.push(call)
    const custom = await responder?.(call)
    if (custom) return custom
    if (call.method !== 'GET') throw new Error(`Unexpected mutation: ${call.method} ${call.path}`)
    if (call.path === '/api/auth/me') return json(actor)
    if (call.path === '/api/catalog') return json(catalogFixture)
    if (call.path === '/api/batches') return json([recoveryFixture.batch])
    if (call.path === '/api/returns') return json(recoveryFixture.returns)
    if (call.path === '/api/inventory') return json(inventory)
    if (call.path === '/api/plans?limit=50') return json([])
    if (call.path === `/api/components/${componentId}/history`) return json(history)
    if (call.path === `/api/components/${componentId}/images`) return json([])
    if (call.path === '/api/inference/status') return json({ status: 'unavailable', busy: false, provider: null, model_repository: null, model_revision: null, device: null })
    if (call.path === `/api/components/${componentId}/inference`) return json([])
    if (call.path.startsWith(`/api/components/${componentId}/compatibility?`)) return json({ compatible: false, reasons: ['Component identity requires operator verification.'] })
    throw new Error(`Unexpected request: ${call.method} ${call.path}`)
  }))
  return calls
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function signIn() {
  const user = userEvent.setup()
  render(<App />)
  await user.type(screen.getByLabelText('Operator token'), token)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  await screen.findByRole('button', { name: 'Sign out' })
  return user
}

describe('operator authentication', () => {
  it('keeps bearer credentials out of browser storage, URLs, and rendered workspace', async () => {
    const calls = transport()
    const localWrite = vi.spyOn(Storage.prototype, 'setItem')
    await signIn()
    expect(calls.find(call => call.path === '/api/auth/me')?.init.headers).toBeDefined()
    for (const call of calls) {
      expect(new Headers(call.init.headers).get('Authorization')).toBe(`Bearer ${token}`)
      expect(call.path).not.toContain(token)
    }
    expect(localWrite).not.toHaveBeenCalled()
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    expect(window.location.href).not.toContain(token)
    expect(document.body.textContent).not.toContain(token)
  })

  it('rejects a failed sign-in and renders backend error text without interpreting markup', async () => {
    const message = '<img src=x onerror=alert(1)> Invalid operator credential.'
    const calls = transport(call => call.path === '/api/auth/me' ? json({ detail: message }, 401) : undefined)
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Operator token'), token)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
    expect(calls.map(call => call.path)).toEqual(['/api/auth/me'])
    expect(localStorage.length + sessionStorage.length).toBe(0)
  })

  it('sign-out discards the private workspace and requires a new credential', async () => {
    transport()
    const user = await signIn()
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(screen.getByLabelText('Operator token')).toHaveValue('')
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
    expect(screen.queryByText(componentId)).not.toBeInTheDocument()
    expect(localStorage.length + sessionStorage.length).toBe(0)
  })

  it('ignores a late rejected request from an old session after another operator signs in', async () => {
    let rejectOldRequest!: (response: Response) => void
    const oldRequest = new Promise<Response>(resolve => { rejectOldRequest = resolve })
    let inventoryReads = 0
    let signIns = 0
    transport(call => {
      if (call.path === '/api/auth/me') return json(++signIns === 1 ? actor : { ...actor, actor_id: 'second-operator', roles: ['viewer'] })
      if (call.path === '/api/inventory' && ++inventoryReads === 1) return oldRequest
      return undefined
    })
    const user = await signIn()
    await waitFor(() => expect(inventoryReads).toBe(1))
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    await user.type(screen.getByLabelText('Operator token'), 'a-different-in-memory-operator-token')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByText('second-operator')
    expect(await screen.findByRole('button', { name: 'Register batch' })).toBeDisabled()
    await act(async () => { rejectOldRequest(json({ detail: 'Old operator credential was revoked.' }, 401)) })
    await waitFor(() => expect(inventoryReads).toBe(2))
    expect(screen.getByText('second-operator')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
    expect(screen.queryByText('Old operator credential was revoked.')).not.toBeInTheDocument()
  })
})

async function openReview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /Component review/ }))
  await user.selectOptions(await screen.findByLabelText('Component to review'), componentId)
  await screen.findByLabelText('Review reason')
}

describe('physical intake and human evidence review', () => {
  it('disables intake and verification mutations for a viewer-only operator', async () => {
    const calls = transport(call => call.path === '/api/auth/me' ? json({ ...actor, roles: ['viewer'] }) : undefined)
    const user = await signIn()
    expect(await screen.findByRole('button', { name: 'Register component' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Register batch' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Upload images' })).toBeDisabled()
    await openReview(user)
    expect(screen.getByRole('button', { name: 'Verify component' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: /Recovery planning/ }))
    expect(await screen.findByRole('button', { name: 'Generate recovery plan' })).toBeDisabled()
    expect(calls.filter(call => call.method !== 'GET')).toEqual([])
  })

  it('registers one explicit physical identifier against the chosen source return', async () => {
    const calls = transport(call => {
      if (call.method === 'POST' && call.path === '/api/components') return json(JSON.parse(String(call.init.body)), 201)
      if (call.path === '/api/components/physical-new-item/images') return json([])
      return undefined
    })
    const user = await signIn()
    await user.selectOptions(await screen.findByLabelText('Source return'), firstRecord.component.source_return_id)
    await user.type(screen.getByLabelText(/^Physical component ID/), 'physical-new-item')
    await user.click(screen.getByRole('button', { name: 'Register component' }))
    await screen.findByText('Intake record registered. Identity still requires evidence and review.')
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(1)
    const body = JSON.parse(String(writes[0].init.body))
    expect(body).toEqual({ physical_component_id: 'physical-new-item', source_return_id: firstRecord.component.source_return_id, registered_at: expect.any(String) })
    expect(Number.isNaN(Date.parse(body.registered_at))).toBe(false)
  })

  it('uploads multiple raw views to the same existing component without creating stock', async () => {
    const calls = transport(call => call.method === 'POST' && call.path.includes('/images?') ? json({ duplicate: false }, 201) : undefined)
    const user = await signIn()
    await user.selectOptions(await screen.findByLabelText('Component to photograph'), componentId)
    const files = [new File(['front'], 'front.png', { type: 'image/png' }), new File(['back'], 'back.webp', { type: 'image/webp' })]
    const input = screen.getByLabelText(/^Component images/) as HTMLInputElement
    expect(input.validity.valueMissing).toBe(true)
    selectNativeFiles(input, files)
    expect(input.files).toHaveLength(2)
    expect(input.validity.valid).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Upload images' }))
    await screen.findByText(/No additional physical stock was created/)
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes.map(call => call.path)).toEqual(Array(2).fill(`/api/components/${componentId}/images?return_id=${firstRecord.component.source_return_id}`))
    expect(writes.map(call => call.init.body)).toEqual(files)
    expect(writes.map(call => new Headers(call.init.headers).get('Content-Type'))).toEqual(['image/png', 'image/webp'])
  })

  it('reports a duplicate image as reused evidence without registering another component', async () => {
    const calls = transport(call => call.method === 'POST' && call.path.includes('/images?') ? json({ duplicate: true }) : undefined)
    const user = await signIn()
    await user.selectOptions(await screen.findByLabelText('Component to photograph'), componentId)
    const input = screen.getByLabelText(/^Component images/) as HTMLInputElement
    const file = new File(['existing-image'], 'existing.png', { type: 'image/png' })
    selectNativeFiles(input, [file])
    expect(input.validity.valid).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Upload images' }))
    expect(await screen.findByText(/1 duplicate upload\(s\) reused existing evidence/)).toHaveTextContent('No additional physical stock was created.')
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(1)
    expect(writes[0].path).toBe(`/api/components/${componentId}/images?return_id=${firstRecord.component.source_return_id}`)
    expect(writes[0].init.body).toBe(file)
  })

  it.each([
    { status: 415, type: 'text/plain', name: 'unsupported.txt', detail: 'Use image/jpeg, image/png, or image/webp.' },
    { status: 422, type: 'image/png', name: 'corrupt.png', detail: 'The uploaded bytes are not a valid supported image.' },
    { status: 503, type: 'image/png', name: 'pending.png', detail: 'Image storage is temporarily unavailable.' },
  ])('displays upload failure $status and retains the selection without claiming success', async failure => {
    const calls = transport(call => call.method === 'POST' && call.path.includes('/images?') ? json({ detail: failure.detail }, failure.status) : undefined)
    const user = await signIn()
    await user.selectOptions(await screen.findByLabelText('Component to photograph'), componentId)
    const input = screen.getByLabelText(/^Component images/) as HTMLInputElement
    const file = new File(['synthetic-rejected-input'], failure.name, { type: failure.type })
    // `accept` guides a real file picker; server validation still decides whether
    // selected bytes and media type are admissible. It is not a validity flag.
    selectNativeFiles(input, [file])
    expect(input.validity.valid).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Upload images' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(failure.detail)
    expect(screen.queryByText(/Image evidence saved/)).not.toBeInTheDocument()
    expect(input.files).toHaveLength(1)
    expect(input.files?.item(0)).toBe(file)
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(1)
  })

  it('clears the session when the backend rejects upload authority with 401', async () => {
    const calls = transport(call => call.method === 'POST' && call.path.includes('/images?') ? json({ detail: 'Valid bearer authentication is required.' }, 401) : undefined)
    const user = await signIn()
    await user.selectOptions(await screen.findByLabelText('Component to photograph'), componentId)
    const input = screen.getByLabelText(/^Component images/) as HTMLInputElement
    selectNativeFiles(input, [new File(['image'], 'view.png', { type: 'image/png' })])
    expect(input.validity.valid).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Upload images' }))
    expect(await screen.findByLabelText('Operator token')).toHaveValue('')
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Image evidence saved/)).not.toBeInTheDocument()
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(1)
    expect(localStorage.length + sessionStorage.length).toBe(0)
  })

  it.each(['initial verification', 'identity correction'])('sends current evidence version and provenance for %s without an operator override', async mode => {
    const correcting = mode === 'identity correction'
    const loaded = {
      ...clone(history), current: {
        ...clone(history.current), version: correcting ? 7 : 2, state: correcting ? 'verified' : 'unresolved',
        verification: correcting ? { ...clone(firstRecord.verification), supersedes_verification_id: null } : null,
      },
    }
    const calls = transport(call => {
      if (call.path === `/api/components/${componentId}/history`) return json(loaded)
      if (call.method === 'POST' && call.path.endsWith('/verification')) return json(loaded.current)
      return undefined
    })
    const user = await signIn()
    await openReview(user)
    await user.selectOptions(screen.getByLabelText('Component type'), 'body')
    await user.selectOptions(screen.getByLabelText('Revision'), 'A')
    await user.selectOptions(screen.getByLabelText('Visible condition'), 'acceptable')
    if (!correcting) await user.click(screen.getByRole('checkbox', { name: new RegExp(firstRecord.observation.observation_id) }))
    await user.type(screen.getByLabelText('Review reason'), 'Visible marking checked against approved catalog.')
    await user.click(screen.getByRole('button', { name: correcting ? 'Record correction' : 'Verify component' }))
    await screen.findByText('Human verification recorded with its evidence links and actor identity.')
    const write = calls.find(call => call.method === 'POST')!
    expect(write.path).toBe(`/api/components/${componentId}/verification`)
    const body = JSON.parse(String(write.init.body))
    expect(body.expected_version).toBe(correcting ? 7 : 2)
    expect(body.verification).toMatchObject({
      physical_component_id: componentId, identity: { component_type_id: 'body', revision: 'A' },
      visible_condition: 'acceptable', evidence_observation_ids: [firstRecord.observation.observation_id],
      supersedes_verification_id: correcting ? firstRecord.verification.verification_id : null,
    })
    expect(body.verification.verification_id).toEqual(expect.any(String))
    expect(body.verification).not.toHaveProperty('operator_id')
  })

  it('shows a stale verification conflict and reloads authoritative evidence without claiming success', async () => {
    let stale = false
    const calls = transport(call => {
      if (call.path === `/api/components/${componentId}/history`) return json(stale ? { ...history, current: { ...history.current, version: 3, state: 'review_required', unresolved_reasons: ['New evidence requires review.'] } } : history)
      if (call.method === 'POST' && call.path.endsWith('/verification')) { stale = true; return json({ detail: 'Evidence version changed.' }, 409) }
      return undefined
    })
    const user = await signIn()
    await openReview(user)
    await user.selectOptions(screen.getByLabelText('Component type'), 'body')
    await user.selectOptions(screen.getByLabelText('Revision'), 'A')
    await user.click(screen.getByRole('checkbox', { name: new RegExp(firstRecord.observation.observation_id) }))
    await user.type(screen.getByLabelText('Review reason'), 'Review based on the visible evidence.')
    await user.click(screen.getByRole('button', { name: 'Verify component' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('State conflict: Evidence version changed. Refresh the current record before retrying.')
    expect(await screen.findByText(/Evidence version 3/)).toBeInTheDocument()
    expect(screen.queryByText('Human verification recorded with its evidence links and actor identity.')).not.toBeInTheDocument()
    expect(calls.filter(call => call.path.endsWith('/verification'))).toHaveLength(1)
  })
})

async function openPlan(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /Execution/ }))
  await user.click(await screen.findByRole('button', { name: 'Open plan' }))
  await screen.findByText('Plan version 1')
}

describe('scenario planning and explicit execution', () => {
  it('does not open a previous operator plan when its response arrives after another operator signs in', async () => {
    let resolvePlan!: (response: Response) => void
    const pendingPlan = new Promise<Response>(resolve => { resolvePlan = resolve })
    let signIns = 0
    const calls = transport(call => {
      if (call.path === '/api/auth/me') return json(++signIns === 1 ? actor : { ...actor, actor_id: 'second-operator', roles: ['viewer'] })
      if (call.method === 'POST' && call.path === '/api/plans') return pendingPlan
      return undefined
    })
    const user = await signIn()
    await user.click(screen.getByRole('button', { name: /Recovery planning/ }))
    await user.type(await screen.findByLabelText('Scenario description'), 'First operator private scenario.')
    await user.type(screen.getByLabelText('Labor cost per minute (cents)'), '25')
    await user.type(screen.getByLabelText(`Donor value (cents) — ${componentId}`), '600')
    await user.click(screen.getByRole('button', { name: 'Generate recovery plan' }))
    await waitFor(() => expect(calls.filter(call => call.method === 'POST' && call.path === '/api/plans')).toHaveLength(1))
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    await user.type(screen.getByLabelText('Operator token'), 'second-operator-memory-token')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByText('second-operator')
    expect(await screen.findByRole('button', { name: 'Generate recovery plan' })).toBeDisabled()
    await act(async () => { resolvePlan(json(samplePlan, 201)) })
    expect(screen.getByRole('heading', { name: 'Recovery planning', level: 1 })).toBeInTheDocument()
    expect(screen.getByText('second-operator')).toBeInTheDocument()
    expect(calls.some(call => call.path === `/api/plans/${samplePlan.plan.plan_id}`)).toBe(false)
    expect(screen.queryByText('Recovery proposal generated from the current inventory and server-approved policies.')).not.toBeInTheDocument()
  })

  it('requires explicit economic inputs and posts only scenario estimates before displaying server plan and audit', async () => {
    let created = false
    const calls = transport(call => {
      if (call.path === '/api/inventory') return json({ items: samplePlan.plan.problem.inventory.map(item => ({ item, availability: 'available', plan_id: null, action_id: null })), completed_kits: [] })
      if (call.path === '/api/plans' && call.method === 'POST') { created = true; return json(samplePlan, 201) }
      if (call.path === '/api/plans?limit=50') return json(created ? [summary] : [])
      if (call.path === `/api/plans/${samplePlan.plan.plan_id}`) return json(samplePlan)
      if (call.path === `/api/plans/${samplePlan.plan.plan_id}/audit`) return json(sampleAudit)
      return undefined
    })
    const user = await signIn()
    await user.click(screen.getByRole('button', { name: /Recovery planning/ }))
    const donor = await screen.findByLabelText(`Donor value (cents) — ${componentId}`)
    expect(donor).toHaveValue(null)
    await user.click(screen.getByRole('button', { name: 'Generate recovery plan' }))
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(0)
    await user.type(screen.getByLabelText('Scenario description'), 'Synthetic browser test estimates.')
    await user.type(screen.getByLabelText('Labor cost per minute (cents)'), '25')
    await user.type(screen.getByLabelText(/^Labor capacity/), '60')
    await user.click(screen.getByRole('checkbox', { name: /Include standard-kit/ }))
    await user.type(screen.getByLabelText('Selling price (cents) — standard-kit'), '10000')
    await user.type(screen.getByLabelText('Rebuild labor (minutes) — standard-kit'), '30')
    await user.type(screen.getByLabelText('Other costs (cents) — standard-kit'), '500')
    await user.type(screen.getByLabelText('Demand limit — standard-kit'), '1')
    await user.type(donor, '600')
    await user.type(screen.getByLabelText(`Donor value (cents) — ${recoveryFixture.components[2].component.physical_component_id}`), '200')
    await user.click(screen.getByRole('button', { name: 'Generate recovery plan' }))
    await screen.findByText('Plan version 1')
    const write = calls.find(call => call.method === 'POST')!
    expect(write.path).toBe('/api/plans')
    const body = JSON.parse(String(write.init.body))
    expect(Object.keys(body).sort()).toEqual(['scenario', 'settings'])
    expect(body.scenario).toMatchObject({ description: 'Synthetic browser test estimates.', currency: 'USD', labor_cost_per_minute_cents: 25, labor_capacity_minutes: 60, scenario_estimate: true })
    expect(body.scenario.kits).toEqual([{ configuration_id: 'standard-kit', selling_price_cents: 10000, labor_minutes: 30, other_cost_cents: 500, demand_limit: 1 }])
    expect(body.scenario.components).toEqual([
      { physical_component_id: componentId, donor_value_cents: 600, salvage_value_cents: 0, salvage_labor_minutes: 0 },
      { physical_component_id: recoveryFixture.components[2].component.physical_component_id, donor_value_cents: 200, salvage_value_cents: 0, salvage_labor_minutes: 0 },
    ])
    expect(body).not.toHaveProperty('operator_id')
    expect(screen.getByText('Synthetic scenario review.')).toBeInTheDocument()
    expect(screen.getByText('Estimated net cash recovery')).toBeInTheDocument()
    expect(screen.getByText('Estimated recovery value')).toBeInTheDocument()
    expect(screen.getByText('Review the selected physical components and estimated costs below, then approve and reserve when ready.')).toBeInTheDocument()
    const selectedActions = screen.getByRole('heading', { name: 'Selected recovery actions' })
    const approval = screen.getByRole('heading', { name: 'Approval & reservation' })
    expect(selectedActions.compareDocumentPosition(approval) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getAllByText('USD 87.50').length).toBeGreaterThan(0)
    expect(calls.filter(call => call.path.endsWith('/audit'))).toHaveLength(1)
    expect(calls.some(call => call.path.endsWith('/approve'))).toBe(false)
  })

  it('reloads a conflicted approval and uses the new plan version without completing work automatically', async () => {
    let stored = clone(samplePlan)
    let attempts = 0
    const calls = transport(call => {
      if (call.path === '/api/plans?limit=50') return json([summary])
      if (call.path === `/api/plans/${samplePlan.plan.plan_id}`) return json(stored)
      if (call.path.endsWith('/audit')) return json(sampleAudit)
      if (call.path.endsWith('/approve') && call.method === 'POST') {
        attempts++
        stored = { ...stored, version: stored.version + 1, state: attempts === 1 ? 'proposed' : 'approved' }
        return attempts === 1 ? json({ detail: 'Plan version changed.' }, 409) : json(stored)
      }
      return undefined
    })
    const user = await signIn()
    await openPlan(user)
    expect(screen.queryByText('Confirm kit rebuild completion')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Approval or cancellation reason'), 'Reviewed the exact proposed allocation.')
    await user.click(screen.getByRole('button', { name: 'Approve and reserve' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('State conflict: Plan version changed.')
    await screen.findByText('Plan version 2')
    expect(screen.queryByText('Confirm kit rebuild completion')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Approve and reserve' }))
    await screen.findByText('Approval recorded. Consuming actions reserved their physical components atomically.')
    expect(screen.getByText('Plan version 3')).toBeInTheDocument()
    expect(screen.getByText('Confirm kit rebuild completion')).toBeInTheDocument()
    expect(screen.getByText('Components reserved. Confirm each completed action below. Remaining confirmations: 1.')).toBeInTheDocument()
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes.map(call => JSON.parse(String(call.init.body)).expected_version)).toEqual([1, 2])
    for (const write of writes) {
      expect(write.path).toBe(`/api/plans/${samplePlan.plan.plan_id}/approve`)
      expect(JSON.parse(String(write.init.body))).not.toHaveProperty('operator_id')
    }
    expect(calls.some(call => call.path.endsWith('/complete'))).toBe(false)
  })

  it('requires all physical checks and explicit confirmation before posting completion evidence and exact identities', async () => {
    let stored = { ...clone(samplePlan), state: 'approved', version: 2 }
    const calls = transport(call => {
      if (call.path === '/api/plans?limit=50') return json([{ ...summary, state: 'approved', version: 2 }])
      if (call.path === `/api/plans/${samplePlan.plan.plan_id}`) return json(stored)
      if (call.path.endsWith('/audit')) return json(sampleAudit)
      if (call.method === 'POST' && call.path.endsWith('/complete')) {
        stored = { ...stored, state: 'completed', version: 3, completed_action_ids: [samplePlan.plan.selected_actions[0].action_id] }
        return json(stored)
      }
      return undefined
    })
    const user = await signIn()
    await user.click(screen.getByRole('button', { name: /Execution/ }))
    await user.click(await screen.findByRole('button', { name: 'Open plan' }))
    await user.click(await screen.findByText('Confirm kit rebuild completion'))
    const button = screen.getByRole('button', { name: 'Record completion' })
    expect(button).toBeDisabled()
    await user.type(screen.getByLabelText('Completed kit ID'), 'synthetic-confirmed-kit')
    await user.type(screen.getByLabelText(/^Completion evidence references/), 'internal-work-order:synthetic-confirmation')
    await user.type(screen.getByLabelText('Completion reason'), 'I checked the physical kit against the instruction.')
    for (const id of samplePlan.plan.selected_actions[0].component_ids) {
      await user.click(screen.getByRole('checkbox', { name: `I checked physical component ${id}` }))
    }
    expect(button).toBeDisabled()
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(0)
    await user.click(screen.getByRole('checkbox', { name: 'I confirm this physical action is complete.' }))
    expect(button).toBeEnabled()
    await user.click(button)
    await screen.findByText('Action completion recorded. Physical identities and kit lineage are retained.')
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(1)
    expect(writes[0].path).toBe(`/api/plans/${samplePlan.plan.plan_id}/actions/${samplePlan.plan.selected_actions[0].action_id}/complete`)
    const body = JSON.parse(String(writes[0].init.body))
    expect(body).toMatchObject({ expected_version: 2, confirmed: true, component_ids: samplePlan.plan.selected_actions[0].component_ids, evidence_references: ['internal-work-order:synthetic-confirmation'], completed_kit_id: 'synthetic-confirmed-kit' })
    expect(body).not.toHaveProperty('operator_id')
    expect(screen.queryByRole('button', { name: 'Record completion' })).not.toBeInTheDocument()
    expect(screen.getByText('Plan version 3')).toBeInTheDocument()
    expect(screen.getByText('Recovery recorded. Open Inventory to inspect completed kits and their component history.')).toBeInTheDocument()
  })

  it('explains a cancelled plan without offering completion or approving it again', async () => {
    const calls = transport(call => {
      if (call.path === '/api/plans?limit=50') return json([{ ...summary, state: 'cancelled' }])
      if (call.path === `/api/plans/${samplePlan.plan.plan_id}`) return json({ ...samplePlan, state: 'cancelled' })
      if (call.path.endsWith('/audit')) return json(sampleAudit)
      return undefined
    })
    const user = await signIn()
    await openPlan(user)
    expect(screen.getByText('Plan cancelled. Create a new plan from current inventory before doing any recovery work.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve and reserve' })).toBeDisabled()
    expect(screen.queryByText('Confirm kit rebuild completion')).not.toBeInTheDocument()
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(0)
  })
})
