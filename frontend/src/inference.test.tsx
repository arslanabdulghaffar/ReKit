import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import catalogFixture from '../../tests/fixtures/synthetic_catalog.json'
import { ApiClient } from './api'
import { Review } from './evidence'
import { InferencePanel } from './inference'
import type { Actor, Catalog, EvidenceHistory, ImageAsset, InferenceRun, InferenceStatus, WorkspaceData } from './types'
import { selectNativeFiles } from './test/setup'

// Controlled HTTP responses test UI contracts only, not GPU inference or model accuracy.
const componentId = 'controlled-physical-item'
const actor: Actor = { actor_id: 'controlled-reviewer', kind: 'human', roles: ['viewer', 'reviewer', 'intake'] }
const assets: ImageAsset[] = ['a', 'b', 'c'].map((letter, index) => ({
  asset_id: `asset-${letter.repeat(32)}`, physical_component_id: componentId, return_id: 'controlled-return',
  sha256: letter.repeat(64), byte_size: 100, media_type: 'image/png', width: 24, height: 18,
  received_at: '2026-10-13T00:00:00Z', uploaded_by: actor.actor_id,
  observation_id: `controlled-capture-${index + 1}`, availability: 'available',
}))
const history: EvidenceHistory = {
  component: { physical_component_id: componentId, source_return_id: 'controlled-return', registered_at: '2026-10-13T00:00:00Z' },
  current: { physical_component_id: componentId, version: 7, state: 'review_required', verification: null, unresolved_reasons: ['Human review required.'] },
  events: assets.map((asset, index) => ({
    sequence: index + 1, event_id: asset.observation_id, kind: 'observation', recorded_at: asset.received_at,
    payload: { observation_id: asset.observation_id, physical_component_id: componentId, source_return_id: 'controlled-return',
      evidence_reference: `asset:${asset.asset_id}`, source: 'operator', source_reference: actor.actor_id },
  })),
}
const ready = { status: 'ready' as const, busy: false, provider: 'controlled-test-double', model_repository: 'controlled/vision', model_revision: 'd'.repeat(40), device: 'cpu-test-double' }

function completedRun(): InferenceRun {
  return {
    start: {
      run_id: 'controlled-inference-run', request_id: 'controlled-request', actor_id: actor.actor_id,
      physical_component_id: componentId, source_return_id: 'controlled-return', evidence_version: 4,
      inputs: assets.slice(0, 2).map(asset => ({ asset_id: asset.asset_id, sha256: asset.sha256, observation_id: asset.observation_id })),
      started_at: '2026-10-13T00:01:00Z', configuration: {
        provider: ready.provider, model_repository: ready.model_repository, model_revision: ready.model_revision,
        processor_revision: ready.model_revision, runtime: { engine: 'controlled CPU test double' }, device: ready.device,
        prompt_version: 'controlled-v1', preprocessing: { max_images: 2 }, generation: { max_new_tokens: 128 },
      },
    },
    outcome: {
      run_id: 'controlled-inference-run', status: 'succeeded', completed_at: '2026-10-13T00:01:01Z',
      output: {
        observations: [{ kind: 'appearance', text: 'Controlled blue housing observation.', image_indices: [1] }],
        candidates: [{ component_type_id: 'body', revision: 'A', revision_marking: 'A', reason: 'Controlled visible marking fixture.', image_indices: [1] }],
        uncertainties: ['The hidden interior is not visible.'],
        additional_views: [{ view: 'Connector close-up', reason: 'The connector marking is unreadable.', image_indices: [2] }],
      },
      raw_output: 'Controlled test fixture, not real model output.', failure_reason: null,
      metrics: { test_double: true }, stale: false, stale_reason: null,
      applied_event_ids: ['controlled-model-observation', 'controlled-model-proposal', 'controlled-model-review'], evidence_version_after: 7,
    },
  }
}

type Call = { path: string; method: string; init: RequestInit }
type Responder = (call: Call) => Response | undefined | Promise<Response | undefined>
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })

function transport(runs: InferenceRun[] = [], responder?: Responder, status: InferenceStatus = ready) {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const call = { path: String(input), method: init.method ?? 'GET', init }
    calls.push(call)
    const custom = await responder?.(call)
    if (custom) return custom
    if (call.method !== 'GET') throw new Error(`Unexpected mutation: ${call.path}`)
    if (call.path === '/api/inference/status') return json(status)
    if (call.path === `/api/components/${componentId}/inference`) return json(runs)
    if (call.path.startsWith('/api/assets/') && call.path.endsWith('/content')) return new Response('controlled-image-bytes', { headers: { 'Content-Type': 'image/png' } })
    if (call.path === '/api/inference/controlled-inference-run' && runs.length) return json(runs[0])
    throw new Error(`Unexpected request: ${call.path}`)
  }))
  return calls
}

function props() {
  return {
    api: new ApiClient('controlled-memory-only-token'), actor, componentId, history: structuredClone(history),
    assets: structuredClone(assets), locked: false, catalog: catalogFixture as Catalog,
    onUpdated: vi.fn(async () => {}), onProposal: vi.fn(),
  }
}

const originalCreate = URL.createObjectURL
const originalRevoke = URL.revokeObjectURL
beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:controlled-private-image')
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => {
  cleanup()
  URL.createObjectURL = originalCreate
  URL.revokeObjectURL = originalRevoke
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function chooseImage(user: ReturnType<typeof userEvent.setup>, index = 0) {
  await user.click(await screen.findByRole('checkbox', { name: `Analyze image ${assets[index].asset_id}` }))
}

describe('unverified inspection evidence', () => {
  it('shows actual model provenance, supported images, uncertainty and requested views without verifying', async () => {
    const calls = transport([completedRun()])
    const properties = props()
    render(<InferencePanel {...properties} />)
    expect(await screen.findByText('Controlled blue housing observation.')).toBeInTheDocument()
    expect(screen.getAllByText('controlled/vision').length).toBeGreaterThan(0)
    expect(screen.getByText('The hidden interior is not visible.')).toBeInTheDocument()
    expect(screen.getByText('Connector close-up')).toBeInTheDocument()
    expect(screen.getByText('The connector marking is unreadable.')).toBeInTheDocument()
    expect(screen.getAllByText(/unverified/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Review proposal body A' })).toBeEnabled()
    expect(properties.onProposal).not.toHaveBeenCalled()
    expect(calls.filter(call => call.method !== 'GET')).toEqual([])
  })

  it('labels remote revisions as configured without asserting deployed weights or AMD hardware', async () => {
    const remote = { ...ready, provider: 'openai-remote', device: 'remote' }
    const run = completedRun()
    Object.assign(run.start.configuration, { provider: remote.provider, device: remote.device })
    transport([run], undefined, remote)
    render(<InferencePanel {...props()} />)
    expect(await screen.findByText(`Configured revision ${remote.model_revision}`)).toBeInTheDocument()
    expect(await screen.findByText(/^Run model:/)).toHaveTextContent(`Configured revision ${remote.model_revision}`)
    expect(screen.getAllByText(/Remote responses are checked for the configured model ID/)).toHaveLength(1)
    expect(screen.getByText(/The response does not verify deployed weights, runtime, or AMD hardware/)).toBeInTheDocument()
  })

  it.each(['configured', 'unavailable'] as const)('shows %s TokenFactory configuration without inventing revisions or a successful run', async status => {
    const shared = { ...ready, status, provider: 'amd-tokenfactory', model_repository: 'controlled/shared-vision', model_revision: null, device: 'remote' }
    const calls = transport([], undefined, shared)
    const properties = props()
    render(<InferencePanel {...properties} />)
    expect(await screen.findByText('controlled/shared-vision')).toBeInTheDocument()
    expect(screen.getByText('amd-tokenfactory · remote')).toBeInTheDocument()
    expect(screen.getByText('Weight/processor revision not attested by shared service')).toBeInTheDocument()
    expect(screen.getByText(/Its GPU model and server runtime remain unverified/)).toBeInTheDocument()
    expect(screen.queryByText(/Configured revision|^Run model:|Analysis finished/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analyze images' })).toBeDisabled()
    if (status === 'unavailable') expect(screen.getByText(/no AI fallback is used/)).toBeInTheDocument()
    expect(properties.onProposal).not.toHaveBeenCalled()
    expect(calls.filter(call => call.method !== 'GET')).toEqual([])
  })

  it('preserves a TokenFactory run and source evidence as unverified with unattested revisions', async () => {
    const shared = { ...ready, provider: 'amd-tokenfactory', model_repository: 'controlled/shared-vision', model_revision: null, device: 'remote' }
    const run = completedRun()
    Object.assign(run.start.configuration, { provider: shared.provider, model_repository: shared.model_repository,
      device: shared.device, model_revision: null, processor_revision: null,
      runtime: { revision_verification: 'shared_service_unattested', remote_runtime: 'unknown', hardware_verification: 'unverified' } })
    const calls = transport([run], undefined, shared)
    const properties = props()
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    expect(await screen.findByText(/^Run model:/)).toHaveTextContent('controlled/shared-vision · amd-tokenfactory · remote · Weight/processor revision not attested by shared service')
    expect(screen.getByText('Controlled blue housing observation.')).toBeInTheDocument()
    expect(screen.getByText(/The response does not verify deployed weights, runtime, or AMD hardware/)).toBeInTheDocument()
    await user.click(screen.getByText('Source images & run provenance'))
    expect(screen.getAllByText(`SHA-256 ${assets[0].sha256}`)[0]).toBeVisible()
    expect(screen.getAllByText(`SHA-256 ${assets[1].sha256}`)[0]).toBeVisible()
    expect(screen.queryByText(/Configured revision/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review proposal body A' })).toBeEnabled()
    expect(properties.onProposal).not.toHaveBeenCalled()
    expect(calls.filter(call => call.method !== 'GET')).toEqual([])
  })

  it('labels a historical TokenFactory run independently of the current pinned local provider', async () => {
    const local = { ...ready, provider: 'local-transformers', device: 'cuda:1' }
    const localRun = completedRun()
    Object.assign(localRun.start.configuration, { provider: local.provider, device: local.device })
    const sharedRun = completedRun()
    sharedRun.start.run_id = 'historical-shared-run'
    sharedRun.outcome!.run_id = sharedRun.start.run_id
    Object.assign(sharedRun.start.configuration, { provider: 'amd-tokenfactory', device: 'remote',
      model_revision: null, processor_revision: null,
      runtime: { revision_verification: 'shared_service_unattested', remote_runtime: 'unknown', hardware_verification: 'unverified' } })
    transport([localRun, sharedRun], undefined, local)
    const user = userEvent.setup()
    render(<InferencePanel {...props()} />)
    const selector = await screen.findByRole('combobox', { name: /^Inspection run/ })
    expect(screen.queryByText(/AMD TokenFactory is a shared remote service/)).not.toBeInTheDocument()
    await user.selectOptions(selector, sharedRun.start.run_id)
    expect(screen.getByText(`Revision ${local.model_revision}`)).toBeInTheDocument()
    expect(screen.getByText(/^Run model:/)).toHaveTextContent('amd-tokenfactory · remote · Weight/processor revision not attested by shared service')
    expect(screen.getByText(/AMD TokenFactory is a shared remote service/)).toBeInTheDocument()
    await user.selectOptions(selector, localRun.start.run_id)
    expect(screen.queryByText(/AMD TokenFactory is a shared remote service/)).not.toBeInTheDocument()
    expect(screen.getByText(/^Run model:/)).toHaveTextContent(`local-transformers · cuda:1 · Revision ${local.model_revision}`)
  })

  it('preserves local model revision wording without remote deployment notices', async () => {
    const local = { ...ready, provider: 'local-transformers', device: 'cuda:1' }
    const run = completedRun()
    Object.assign(run.start.configuration, { provider: local.provider, device: local.device })
    transport([run], undefined, local)
    render(<InferencePanel {...props()} />)
    expect(await screen.findByText(`Revision ${local.model_revision}`)).toBeInTheDocument()
    expect(await screen.findByText(/^Run model:/)).toHaveTextContent(`Revision ${local.model_revision}`)
    expect(screen.queryByText(/Configured revision/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Remote responses are checked/)).not.toBeInTheDocument()
  })

  it('uses the recorded provider for historical provenance after the current provider changes', async () => {
    const local = { ...ready, provider: 'local-transformers', device: 'cuda:1' }
    const localRun = completedRun()
    Object.assign(localRun.start.configuration, { provider: local.provider, device: local.device })
    const remoteRun = completedRun()
    remoteRun.start.run_id = 'historical-remote-run'
    remoteRun.outcome!.run_id = remoteRun.start.run_id
    Object.assign(remoteRun.start.configuration, { provider: 'openai-remote', device: 'remote', model_revision: 'e'.repeat(40) })
    transport([localRun, remoteRun], undefined, local)
    const user = userEvent.setup()
    render(<InferencePanel {...props()} />)
    const selector = await screen.findByRole('combobox', { name: /^Inspection run/ })
    expect(screen.queryByText(/Remote responses are checked/)).not.toBeInTheDocument()
    await user.selectOptions(selector, remoteRun.start.run_id)
    expect(screen.getByText(`Revision ${local.model_revision}`)).toBeInTheDocument()
    expect(screen.getByText(/^Run model:/)).toHaveTextContent(`openai-remote · remote · Configured revision ${'e'.repeat(40)}`)
    expect(screen.getByText(/Remote responses are checked/)).toBeInTheDocument()
    await user.selectOptions(selector, localRun.start.run_id)
    expect(screen.queryByText(/Remote responses are checked/)).not.toBeInTheDocument()
    expect(screen.getByText(/^Run model:/)).toHaveTextContent(`local-transformers · cuda:1 · Revision ${local.model_revision}`)
  })

  it('shows unknown identity and alternatives without silently choosing a candidate', async () => {
    const unknown = completedRun()
    unknown.outcome!.output!.candidates = []
    unknown.outcome!.output!.uncertainties = ['No catalog identity can be established from these images.']
    transport([unknown])
    const properties = props()
    const view = render(<InferencePanel {...properties} />)
    expect(await screen.findByText('No catalog identity can be established from these images.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Review proposal/ })).not.toBeInTheDocument()
    view.unmount()
    const alternatives = completedRun()
    alternatives.outcome!.output!.candidates.push({ component_type_id: 'adapter', revision: 'B', revision_marking: 'B', reason: 'Controlled alternative hypothesis.', image_indices: [2] })
    transport([alternatives])
    render(<InferencePanel {...props()} />)
    expect(await screen.findByRole('button', { name: 'Review proposal body A' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Review proposal adapter B' })).toBeEnabled()
    expect(properties.onProposal).not.toHaveBeenCalled()
  })

  it('does not replace a current human verification with an unknown historical AI result', async () => {
    const run = completedRun()
    run.outcome!.output!.candidates = []
    const calls = transport([run])
    const properties = props()
    properties.history.current = {
      ...properties.history.current, version: 8, state: 'verified', unresolved_reasons: [],
      verification: { verification_id: 'human-reviewed-after-ai', physical_component_id: componentId,
        identity: { component_type_id: 'body', revision: 'A' }, operator_id: actor.actor_id,
        verified_at: '2026-10-13T00:02:00Z', evidence_observation_ids: [assets[0].observation_id],
        visible_condition: 'acceptable', reason: 'Controlled human verification fixture.', supersedes_verification_id: null },
    }
    render(<InferencePanel {...properties} />)
    expect(await screen.findByText(/The current human-verified identity remains in effect/)).toBeInTheDocument()
    expect(screen.getByText(/Stale or historical inspection/)).toBeInTheDocument()
    expect(screen.queryByText(/Identity unknown|Identity remains unverified/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject unsupported proposal' })).toBeDisabled()
    expect(calls.filter(call => call.method !== 'GET')).toEqual([])
  })

  it('only prefills identity after an explicit proposal review click', async () => {
    const run = completedRun()
    const calls = transport([run])
    const properties = props()
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    await user.click(await screen.findByRole('button', { name: 'Review proposal body A' }))
    expect(properties.onProposal).toHaveBeenCalledExactlyOnceWith(run.outcome!.output!.candidates[0])
    expect(calls.filter(call => call.method !== 'GET')).toEqual([])
  })

  it('renders untrusted model text as text rather than executable markup', async () => {
    const run = completedRun()
    const unsafe = '<img src=x onerror=alert(1)> Controlled model text.'
    run.outcome!.output!.observations[0].text = unsafe
    transport([run])
    render(<InferencePanel {...props()} />)
    expect(await screen.findByText(unsafe)).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
  })

  it.each(['invalid_output', 'failed', 'unavailable', 'timed_out'] as const)('shows terminal %s without suggesting a verified identity', async status => {
    const run = completedRun()
    run.outcome = { ...run.outcome!, status, output: null, failure_reason: `Controlled ${status} explanation.`, applied_event_ids: [], evidence_version_after: 4 }
    transport([run])
    const properties = props()
    render(<InferencePanel {...properties} />)
    expect(await screen.findByText(new RegExp(`Controlled ${status} explanation\\.`))).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Review proposal/ })).not.toBeInTheDocument()
    expect(properties.onProposal).not.toHaveBeenCalled()
  })

  it('keeps stale output visible for audit but disables using its identity proposal', async () => {
    const run = completedRun()
    run.outcome!.stale = true
    run.outcome!.stale_reason = 'A newer human correction superseded the input evidence.'
    run.outcome!.applied_event_ids = []
    transport([run])
    render(<InferencePanel {...props()} />)
    expect(await screen.findByText(/A newer human correction superseded the input evidence\./)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review proposal body A' })).toBeDisabled()
  })
})

describe('inspection requests and explicit human actions', () => {
  it('labels gallery views readably and maps reversed selected order to the recorded run inputs', async () => {
    const run = completedRun()
    run.start.inputs.reverse()
    const calls = transport([], call => call.method === 'POST' ? json(run, 202) : undefined)
    const properties = props()
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    await chooseImage(user, 1)
    await chooseImage(user, 0)
    const choice = screen.getByRole('checkbox', { name: `Analyze image ${assets[1].asset_id}` }).closest('label')!
    expect(within(choice).getByText('Image 2')).toBeInTheDocument()
    expect(within(choice).queryByText(assets[1].asset_id)).not.toBeInTheDocument()
    expect(screen.getByText(/Selected order: Image 2 → Image 1/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Analyze images' }))
    expect(await screen.findByText('Controlled blue housing observation.')).toBeInTheDocument()
    expect(screen.getAllByText('Run image 1: Image 2 in the gallery').length).toBeGreaterThan(0)
    expect(screen.getByText('Run image 2: Image 1 in the gallery')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Suggested components — unverified' })).toBeInTheDocument()
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(1)
    expect(JSON.parse(String(writes[0].init.body)).asset_ids).toEqual([assets[1].asset_id, assets[0].asset_id])
    expect(properties.onProposal).not.toHaveBeenCalled()
  })

  it('submits one or two selected asset IDs with the current version and no authority overrides', async () => {
    const calls = transport([], call => call.method === 'POST' && call.path.endsWith('/inference') ? json(completedRun(), 202) : undefined)
    const properties = props()
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    expect(screen.getByRole('button', { name: 'Analyze images' })).toBeDisabled()
    await chooseImage(user)
    await chooseImage(user, 1)
    expect(screen.getByRole('checkbox', { name: `Analyze image ${assets[2].asset_id}` })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Analyze images' }))
    await screen.findByText('Controlled blue housing observation.')
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(1)
    expect(writes[0].path).toBe(`/api/components/${componentId}/inference`)
    expect(JSON.parse(String(writes[0].init.body))).toEqual({
      request_id: expect.stringMatching(/^inspection-/), asset_ids: assets.slice(0, 2).map(asset => asset.asset_id), expected_version: 7,
    })
    expect(properties.onUpdated).toHaveBeenCalledOnce()
    expect(properties.onProposal).not.toHaveBeenCalled()
  })

  it('reuses the exact request ID and evidence version after a lost response', async () => {
    let attempts = 0
    const calls = transport([], call => {
      if (call.method === 'POST' && call.path.endsWith('/inference')) {
        if (++attempts === 1) throw new TypeError('Controlled lost connection')
        return json(completedRun(), 202)
      }
      return undefined
    })
    const user = userEvent.setup()
    render(<InferencePanel {...props()} />)
    await chooseImage(user)
    await user.click(screen.getByRole('button', { name: 'Analyze images' }))
    const retry = await screen.findByRole('button', { name: 'Retry same request' })
    expect(screen.getByRole('button', { name: 'Analyze images' })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: `Analyze image ${assets[0].asset_id}` })).toBeDisabled()
    await user.click(retry)
    await screen.findByText('Controlled blue housing observation.')
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(2)
    expect(writes[1].init.body).toBe(writes[0].init.body)
    expect(screen.queryByRole('button', { name: 'Retry same request' })).not.toBeInTheDocument()
  })

  it('polls a pending run and refreshes evidence only after an actual terminal response', async () => {
    const pending = completedRun()
    pending.outcome = null
    let submitted = false
    let finished = false
    const calls = transport([], call => {
      if (call.method === 'POST' && call.path.endsWith('/inference')) { submitted = true; return json(pending, 202) }
      if (call.path === '/api/inference/status') return json({ ...ready, busy: submitted && !finished })
      if (call.path === '/api/inference/controlled-inference-run') { finished = true; return json(completedRun()) }
      return undefined
    })
    const properties = props()
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    await chooseImage(user)
    await user.click(screen.getByRole('button', { name: 'Analyze images' }))
    expect(await screen.findByText(/Analyzing the selected images/)).toBeInTheDocument()
    expect(properties.onUpdated).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Analyze images' })).toBeDisabled()
    await screen.findByText('Controlled blue housing observation.', {}, { timeout: 4000 })
    expect(properties.onUpdated).toHaveBeenCalledOnce()
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(1)
    expect(calls.some(call => call.path.endsWith('/verification'))).toBe(false)
  })

  it('disables unconfigured inference while retaining manual image intake', async () => {
    const calls = transport([], undefined, { status: 'unavailable', busy: false, provider: null, model_repository: null, model_revision: null, device: null })
    const user = userEvent.setup()
    render(<InferencePanel {...props()} />)
    expect(await screen.findByText(/AI image analysis is unavailable/)).toBeInTheDocument()
    await chooseImage(user)
    expect(screen.getByRole('button', { name: 'Analyze images' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Upload another view' })).toBeEnabled()
    expect(calls.filter(call => call.method !== 'GET')).toEqual([])
    expect(calls.some(call => call.path.endsWith(`/${componentId}/inference`))).toBe(false)
  })

  it('allows an explicit configured-provider retry without assuming successful recovery', async () => {
    const calls = transport([], call => call.method === 'POST' ? json({ detail: 'Configured runtime remains unavailable.' }, 503) : undefined, { ...ready, status: 'unavailable' })
    const user = userEvent.setup()
    render(<InferencePanel {...props()} />)
    expect(await screen.findByText(/A provider is configured/)).toBeInTheDocument()
    await chooseImage(user)
    expect(screen.getByRole('button', { name: 'Analyze images' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Analyze images' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Configured runtime remains unavailable.')
    expect(screen.queryByText('Controlled blue housing observation.')).not.toBeInTheDocument()
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(1)
  })

  it('reads the terminal record when a pending admission races with an idle worker', async () => {
    const pending = completedRun()
    pending.outcome = null
    const calls = transport([], call => {
      if (call.method === 'POST') return json(pending, 202)
      if (call.path === '/api/inference/controlled-inference-run') return json(completedRun())
      return undefined
    })
    const properties = props()
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    await chooseImage(user)
    await user.click(screen.getByRole('button', { name: 'Analyze images' }))
    expect(await screen.findByText('Controlled blue housing observation.')).toBeInTheDocument()
    expect(screen.queryByText(/This pending record has no active worker/)).not.toBeInTheDocument()
    expect(calls.filter(call => call.path === '/api/inference/controlled-inference-run')).toHaveLength(1)
    expect(properties.onUpdated).toHaveBeenCalledOnce()
  })

  it.each(['viewer', 'service', 'allocated'] as const)('disables unauthorized AI decisions for %s', async restriction => {
    const calls = transport([completedRun()])
    const properties = props()
    if (restriction === 'viewer') properties.actor = { ...actor, roles: ['viewer'] }
    if (restriction === 'service') properties.actor = { ...actor, kind: 'service' }
    if (restriction === 'allocated') properties.locked = true
    render(<InferencePanel {...properties} />)
    expect(await screen.findByRole('button', { name: 'Review proposal body A' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Analyze images' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject unsupported proposal' })).toBeDisabled()
    expect(calls.filter(call => call.method !== 'GET')).toEqual([])
  })

  it('surfaces an authorization failure without inventing a result', async () => {
    const calls = transport([], call => call.method === 'POST' ? json({ detail: 'Reviewer authorization was revoked.' }, 401) : undefined)
    const expired = vi.fn()
    const properties = { ...props(), api: new ApiClient('controlled-memory-token', expired) }
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    await chooseImage(user)
    await user.click(screen.getByRole('button', { name: 'Analyze images' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Reviewer authorization was revoked.')
    expect(expired).toHaveBeenCalledOnce()
    expect(properties.onProposal).not.toHaveBeenCalled()
    expect(screen.queryByText('Controlled blue housing observation.')).not.toBeInTheDocument()
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(1)
  })

  it('records rejection only after an explicit reason and retains original model output', async () => {
    const calls = transport([completedRun()], call => call.method === 'POST' && call.path.endsWith('/reject') ? json({ ...history.current, version: 8 }) : undefined)
    const properties = props()
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    const reject = await screen.findByRole('button', { name: 'Reject unsupported proposal' })
    await user.click(reject)
    expect(calls.filter(call => call.method === 'POST')).toEqual([])
    await user.type(screen.getByLabelText(/^Rejection reason/), 'The photographed marking does not support this proposed revision.')
    await user.click(reject)
    expect(await screen.findByText(/Rejection recorded/)).toBeInTheDocument()
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(1)
    expect(writes[0].path).toBe('/api/inference/controlled-inference-run/reject')
    expect(JSON.parse(String(writes[0].init.body))).toEqual({
      rejection_id: expect.stringMatching(/^rejection-/), expected_version: 7,
      reason: 'The photographed marking does not support this proposed revision.',
    })
    expect(screen.getByText('Controlled blue housing observation.')).toBeInTheDocument()
    expect(properties.onUpdated).toHaveBeenCalledOnce()
    expect(properties.onProposal).not.toHaveBeenCalled()
  })

  it('uploads another view against the same physical identity using native file validation', async () => {
    const calls = transport([], call => call.method === 'POST' && call.path.includes('/images?') ? json({ duplicate: false }, 201) : undefined)
    const properties = props()
    const user = userEvent.setup()
    render(<InferencePanel {...properties} />)
    const input = screen.getByLabelText(/^Additional component images/) as HTMLInputElement
    expect(input.validity.valueMissing).toBe(true)
    const image = new File(['controlled-image-bytes'], 'close-up.png', { type: 'image/png' })
    selectNativeFiles(input, [image])
    expect(input.validity.valid).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Upload another view' }))
    await screen.findByText(/No new physical stock was created/)
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(1)
    expect(writes[0].path).toBe(`/api/components/${componentId}/images?return_id=controlled-return`)
    expect(writes[0].init.body).toBe(image)
    expect(properties.onUpdated).toHaveBeenCalledOnce()
  })

  it('ignores a delayed history response after switching physical components', async () => {
    let resolveOld!: (response: Response) => void
    const delayed = new Promise<Response>(resolve => { resolveOld = resolve })
    const nextId = 'another-physical-item'
    const calls = transport([], call => {
      if (call.path === `/api/components/${componentId}/inference`) return delayed
      if (call.path === `/api/components/${nextId}/inference`) return json([])
      return undefined
    })
    const properties = props()
    const view = render(<InferencePanel {...properties} />)
    await waitFor(() => expect(calls.some(call => call.path === `/api/components/${componentId}/inference`)).toBe(true))
    view.rerender(<InferencePanel {...properties} componentId={nextId} assets={[]} history={{
      ...history, component: { ...history.component, physical_component_id: nextId },
      current: { ...history.current, physical_component_id: nextId },
    }} />)
    await waitFor(() => expect(calls.some(call => call.path === `/api/components/${nextId}/inference`)).toBe(true))
    await act(async () => { resolveOld(json([completedRun()])) })
    expect(screen.queryByText('Controlled blue housing observation.')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Review proposal/ })).not.toBeInTheDocument()
    expect(properties.onUpdated).not.toHaveBeenCalled()
  })

  it('requires human correction, visible condition, supporting evidence and explicit verification after proposal prefill', async () => {
    const calls = transport([completedRun()], call => {
      if (call.path === `/api/components/${componentId}/history`) return json(history)
      if (call.path === `/api/components/${componentId}/images`) return json(assets)
      if (call.method === 'POST' && call.path.endsWith('/verification')) return json({ ...history.current, version: 8 })
      return undefined
    })
    const data: WorkspaceData = {
      catalog: catalogFixture as Catalog, batches: [], plans: [],
      returns: [{ return_id: 'controlled-return', batch_id: 'controlled-batch', product_family_id: 'demo-kit', received_at: '2026-10-13T00:00:00Z', declared_configuration_id: null }],
      inventory: { items: [{ item: { component: history.component, evidence: history.current, eligibility: 'held' }, availability: 'held', plan_id: null, action_id: null }], completed_kits: [] },
    }
    const onError = vi.fn()
    const onMessage = vi.fn()
    const user = userEvent.setup()
    render(<Review api={new ApiClient('controlled-memory-only-token')} actor={actor} data={data} componentId={componentId}
      refresh={vi.fn(async () => {})} onError={onError} onMessage={onMessage} onSelect={vi.fn()} />)
    const proposal = await screen.findByRole('button', { name: 'Review proposal body A' })
    const originals = screen.getByRole('heading', { name: 'Views & provenance' })
    const analysis = screen.getByRole('heading', { name: 'AI-assisted inspection' })
    const human = screen.getByRole('heading', { name: 'Human verification' })
    expect(originals.compareDocumentPosition(analysis) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(analysis.compareDocumentPosition(human) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(originals.closest('section')!).getByText('Image 1')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /Image 1.*Operator observation; observation controlled-capture-1/ })).not.toBeChecked()
    await user.click(proposal)
    expect(screen.getByRole('combobox', { name: 'Component type' })).toHaveValue('body')
    expect(screen.getByRole('combobox', { name: 'Revision' })).toHaveValue('A')
    expect(screen.getByRole('combobox', { name: 'Visible condition' })).toHaveValue('unknown')
    expect(screen.getByRole('textbox', { name: 'Review reason' })).toHaveValue('')
    expect(document.querySelectorAll('input[name="observation_id"]:checked')).toHaveLength(0)
    expect(calls.filter(call => call.method === 'POST')).toEqual([])

    await user.selectOptions(screen.getByRole('combobox', { name: 'Component type' }), 'adapter')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Revision' }), 'B')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Visible condition' }), 'acceptable')
    await user.type(screen.getByRole('textbox', { name: 'Review reason' }), 'Human correction: the visible adapter marking is B.')
    await user.click(screen.getByRole('button', { name: 'Verify component' }))
    expect(calls.filter(call => call.method === 'POST')).toEqual([])
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'Select at least one observation supporting this verification.' }))
    await user.click(screen.getByRole('checkbox', { name: /Image 1.*Operator observation; observation controlled-capture-1/ }))
    expect(calls.filter(call => call.method === 'POST')).toEqual([])
    await user.click(screen.getByRole('button', { name: 'Verify component' }))
    await waitFor(() => expect(onMessage).toHaveBeenCalledWith('Human verification recorded with its evidence links and actor identity.'))
    const writes = calls.filter(call => call.method === 'POST')
    expect(writes).toHaveLength(1)
    expect(writes[0].path).toBe(`/api/components/${componentId}/verification`)
    expect(JSON.parse(String(writes[0].init.body))).toEqual({ expected_version: 7, verification: {
      physical_component_id: componentId, identity: { component_type_id: 'adapter', revision: 'B' },
      evidence_observation_ids: ['controlled-capture-1'], visible_condition: 'acceptable',
      reason: 'Human correction: the visible adapter marking is B.', supersedes_verification_id: null,
      verification_id: expect.stringMatching(/^verification-/), verified_at: expect.any(String),
    } })
  })
})
