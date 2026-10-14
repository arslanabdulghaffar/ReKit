import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import type { APIRequestContext, Locator, Page, Response } from '@playwright/test'
import { holdFinalPage } from './demo-presentation'
import type { EvidenceHistory, ImageAsset, InferenceRun, InventorySnapshot, PhysicalComponent, ReturnBatch, ReturnRecord } from '../src/types'

interface ProductSource {
  image_id: string; listing_id: string; group_id: string; split: string; source_url: string
  sha256: string; byte_size: number; width: number; height: number; review_status: string
  marking_visible: null; exact_identity_visually_established: null; revision_supported: null
  source_labels: Record<string, string>
}
interface ProductFixture {
  synthetic: true; simulated_intake: true; real_product_images: true; real_inference: true
  base_url: string; api_url: string; artifacts_dir: string; operator_token: string; viewer_token: string
  operator_id: string; viewer_id: string; model_dir: string; model_revision: string; device: number
  images: Record<string, string[]>; product_sources: ProductSource[]
  dataset: string; dataset_manifest_sha256: string; dataset_attribution: unknown; dataset_source: unknown; dataset_license: unknown
  demo_presentation?: unknown
  fixture: { batch: ReturnBatch; returns: ReturnRecord[]; components: { component: PhysicalComponent }[] }
}

const manifest = JSON.parse(readFileSync(process.env.REKIT_BROWSER_FIXTURE!, 'utf8')) as ProductFixture
if (manifest.synthetic !== true || manifest.simulated_intake !== true || manifest.real_product_images !== true
    || manifest.real_inference !== true || manifest.base_url !== 'http://127.0.0.1:5173'
    || manifest.api_url !== 'http://127.0.0.1:8000' || !/^[a-f0-9]{40}$/.test(manifest.model_revision)
    || !Number.isInteger(manifest.device)) {
  throw new Error('Product acceptance requires an isolated simulated intake with explicit local inference and source records.')
}
const headers = { Authorization: `Bearer ${manifest.operator_token}` }
const escaped = (id: string) => encodeURIComponent(id)
const hash = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex')
const redact = (value: string) => value.replaceAll(manifest.operator_token, '[redacted]').replaceAll(manifest.viewer_token, '[redacted]')
const limitations = [
  'The original ABO catalog images are not photographs of an actual customer return in ReKit.',
  'One physical unit, batch, and return are simulated intake records; source listing membership does not prove physical object identity.',
  'This automated operator-role exercise does not supply independent human ground truth or semantic accuracy labels.',
  'No approved matching product catalog was supplied to inference. Empty candidates demonstrate enforced abstention, not recognition accuracy.',
  'Model observations and image attribution remain unverified; schema validity does not establish their visual truth.',
  'The additional-view request is an operator workflow exercise, not a measurement of AI usefulness.',
  'No kit was rebuilt, reserved, verified, sold, or credited with real recovery value.',
  'Local NVIDIA execution does not qualify AMD hardware, ROCm, or vLLM.',
]

async function get<T>(request: APIRequestContext, route: string): Promise<T> {
  const response = await request.get(`${manifest.api_url}${route}`, { headers })
  expect(response.status(), `GET ${route}`).toBe(200)
  expect(response.headers()['cache-control']).toBe('no-store')
  return response.json() as Promise<T>
}

async function postFromUI(page: Page, button: Locator, route: string, status: number): Promise<Response> {
  const response = page.waitForResponse(item => item.url() === `${manifest.base_url}/api${route}` && item.request().method() === 'POST')
  await button.click()
  const completed = await response
  expect(completed.status(), `POST ${route}`).toBe(status)
  return completed
}

async function capture(page: Page, filename: string): Promise<void> {
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: join(manifest.artifacts_dir, filename), fullPage: true, animations: 'disabled' })
}

async function held(request: APIRequestContext, componentId: string): Promise<{ history: EvidenceHistory; inventory: InventorySnapshot }> {
  const history = await get<EvidenceHistory>(request, `/components/${escaped(componentId)}/history`)
  expect(history.current.verification).toBeNull()
  expect(history.current.state).not.toBe('verified')
  expect(history.events.some(event => event.kind === 'verification')).toBe(false)
  const inventory = await get<InventorySnapshot>(request, '/inventory')
  expect(inventory.items).toHaveLength(1)
  expect(inventory.items[0].item.component.physical_component_id).toBe(componentId)
  expect(inventory.items[0].item.eligibility).toBe('held')
  expect(inventory.items[0].availability).toBe('held')
  expect(inventory.items[0].plan_id).toBeNull()
  expect(inventory.items[0].action_id).toBeNull()
  expect(inventory.completed_kits).toEqual([])
  expect(await get<unknown[]>(request, '/plans')).toEqual([])
  const compatibility = await get<{ compatible: boolean }>(request, `/components/${escaped(componentId)}/compatibility?configuration_id=standard-kit`)
  expect(compatibility.compatible).toBe(false)
  return { history, inventory }
}

test('original catalog product views remain unverified through one real joint inspection and operator rejection', async ({ page, browser, request }) => {
  let stage = 'source validation'
  let run: InferenceRun | null = null
  let finalState: Awaited<ReturnType<typeof held>> | null = null
  let rejection: Record<string, unknown> | null = null
  let passed = false
  let inferencePosts = 0
  const pageErrors: string[] = []
  const screenshots: string[] = []
  const apiChecks: Record<string, number | boolean> = {}
  let assets: ImageAsset[] = []
  page.on('pageerror', error => pageErrors.push(redact(error.message)))
  page.on('request', item => {
    if (item.method() === 'POST' && /\/api\/components\/[^/]+\/inference$/.test(item.url())) inferencePosts++
  })
  const persist = () => writeFileSync(join(manifest.artifacts_dir, 'product-inference-results.json'), redact(JSON.stringify({
    passed, stage, simulated_intake: true, real_product_images: true, real_inference: true,
    independent_human_review: false, semantic_accuracy: null, semantic_accuracy_denominator: 0,
    browser_version: browser.version(), source_records: manifest.product_sources,
    dataset: manifest.dataset, dataset_manifest_sha256: manifest.dataset_manifest_sha256,
    dataset_attribution: manifest.dataset_attribution, dataset_source: manifest.dataset_source, dataset_license: manifest.dataset_license,
    intake_fixture: manifest.fixture, managed_assets: assets, actual_run: run, operator_rejection: rejection,
    final_state: finalState, api_checks: apiChecks, inference_posts: inferencePosts, page_errors: pageErrors,
    screenshots, limitations,
  }, null, 2)), 'utf8')
  try {
    expect(manifest.fixture.returns).toHaveLength(1)
    expect(manifest.fixture.components).toHaveLength(1)
    expect(manifest.dataset).toBe('amazon-berkeley-objects')
    expect(manifest.dataset_manifest_sha256).toMatch(/^[a-f0-9]{64}$/)
    const component = manifest.fixture.components[0].component
    const returned = manifest.fixture.returns[0]
    expect(component.source_return_id).toBe(returned.return_id)
    expect(returned.batch_id).toBe(manifest.fixture.batch.batch_id)
    const paths = manifest.images[component.physical_component_id]
    expect(paths).toHaveLength(2)
    expect(manifest.product_sources.map(source => source.image_id)).toEqual(['71rr7OjqWqL', '812Xgtrv0EL'])
    expect(new Set(manifest.product_sources.map(source => source.group_id)).size).toBe(1)
    for (const [index, source] of manifest.product_sources.entries()) {
      const original = readFileSync(paths[index])
      expect(hash(original)).toBe(source.sha256)
      expect(original.length).toBe(source.byte_size)
      expect(source.group_id).toBe(source.listing_id)
      expect(source.split).toBe('development')
      expect(source.review_status).toBe('pending')
      expect([source.marking_visible, source.exact_identity_visually_established, source.revision_supported]).toEqual([null, null, null])
    }
    persist()
    expect(await get<InventorySnapshot>(request, '/inventory')).toEqual({ items: [], completed_kits: [] })

    stage = 'authenticated simulated intake'
    await page.goto('/')
    await page.getByLabel('Operator token', { exact: true }).fill(manifest.operator_token)
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible()
    await expect(page.getByText(manifest.operator_id, { exact: true })).toBeVisible()
    expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 })
    await page.getByLabel('Batch ID', { exact: true }).fill(manifest.fixture.batch.batch_id)
    await postFromUI(page, page.getByRole('button', { name: 'Register batch', exact: true }), '/batches', 201)
    await page.getByRole('combobox', { name: 'Source batch', exact: true }).selectOption(returned.batch_id)
    await page.getByLabel('Return ID', { exact: true }).fill(returned.return_id)
    await page.getByRole('combobox', { name: 'Product family', exact: true }).selectOption(returned.product_family_id)
    await page.getByRole('combobox', { name: 'Declared configuration', exact: true }).selectOption(returned.declared_configuration_id ?? '')
    await postFromUI(page, page.getByRole('button', { name: 'Register return', exact: true }), '/returns', 201)
    await page.getByRole('combobox', { name: 'Source return', exact: true }).selectOption(returned.return_id)
    await page.getByLabel(/^Physical component ID/).fill(component.physical_component_id)
    await postFromUI(page, page.getByRole('button', { name: 'Register component', exact: true }), '/components', 201)
    expect((await get<ReturnBatch[]>(request, '/batches')).map(batch => batch.batch_id)).toEqual([manifest.fixture.batch.batch_id])
    expect((await get<ReturnRecord[]>(request, '/returns')).map(item => item.return_id)).toEqual([returned.return_id])

    stage = 'original product bytes and managed image lineage'
    await page.getByRole('combobox', { name: 'Component to photograph', exact: true }).selectOption(component.physical_component_id)
    await page.getByLabel(/^Component images/).setInputFiles(paths)
    await page.getByRole('button', { name: 'Upload images', exact: true }).click()
    await expect(page.getByText(`Image evidence saved for ${component.physical_component_id}. No additional physical stock was created.`, { exact: true })).toBeVisible()
    assets = await get<ImageAsset[]>(request, `/components/${escaped(component.physical_component_id)}/images`)
    expect(assets).toHaveLength(2)
    assets = manifest.product_sources.map(source => {
      const matches = assets.filter(asset => asset.sha256 === source.sha256)
      expect(matches).toHaveLength(1)
      const asset = matches[0]
      expect(asset.physical_component_id).toBe(component.physical_component_id)
      expect(asset.return_id).toBe(returned.return_id)
      expect(asset.uploaded_by).toBe(manifest.operator_id)
      expect([asset.byte_size, asset.width, asset.height, asset.media_type]).toEqual([source.byte_size, source.width, source.height, 'image/jpeg'])
      return asset
    })
    for (const asset of assets) {
      const content = await request.get(`${manifest.api_url}/assets/${escaped(asset.asset_id)}/content`, { headers })
      expect(content.status()).toBe(200)
      expect(hash(await content.body())).toBe(asset.sha256)
    }
    const before = await held(request, component.physical_component_id)
    expect(before.history.events).toHaveLength(2)
    for (const asset of assets) {
      const event = before.history.events.find(item => item.event_id === asset.observation_id)
      expect(event?.payload.evidence_reference).toBe(`asset:${asset.asset_id}`)
      expect(event?.payload.source_reference).toBe(manifest.operator_id)
    }
    stage = 'single actual joint inspection'
    await page.getByRole('button', { name: /02.*Component review/ }).click()
    await page.getByRole('combobox', { name: 'Component to review', exact: true }).selectOption(component.physical_component_id)
    const previews = page.getByRole('img', { name: `Evidence for ${component.physical_component_id}`, exact: true })
    await expect(previews).toHaveCount(2)
    await expect.poll(() => previews.evaluateAll(items => items.every(item => item instanceof HTMLImageElement && item.complete && item.naturalWidth > 0))).toBe(true)
    for (const checkbox of await page.getByRole('checkbox', { name: /^Analyze image / }).all()) await checkbox.uncheck()
    for (const asset of assets) await page.getByRole('checkbox', { name: `Analyze image ${asset.asset_id}`, exact: true }).check()
    const admitted = await postFromUI(page, page.getByRole('button', { name: 'Analyze images', exact: true }), `/components/${escaped(component.physical_component_id)}/inference`, 202)
    expect(admitted.request().postDataJSON().asset_ids).toEqual(assets.map(asset => asset.asset_id))
    expect(admitted.request().postDataJSON().expected_version).toBe(before.history.current.version)
    run = await admitted.json() as InferenceRun
    const runId = run.start.run_id
    persist()
    await expect.poll(async () => {
      run = await get<InferenceRun>(request, `/inference/${escaped(runId)}`)
      persist()
      return run.outcome !== null
    }, { timeout: 175_000, intervals: [500, 1000] }).toBe(true)
    // Read once more outside the polling callback so the inspected record and
    // persisted success assertions use the same immutable terminal response.
    run = await get<InferenceRun>(request, `/inference/${escaped(runId)}`)
    persist()
    expect(run.outcome?.status).toBe('succeeded')
    expect(run.outcome?.stale).toBe(false)
    expect(run.start.inputs).toEqual(assets.map(asset => ({ asset_id: asset.asset_id, sha256: asset.sha256, observation_id: asset.observation_id })))
    expect(run.start.actor_id).toBe(manifest.operator_id)
    expect(run.start.physical_component_id).toBe(component.physical_component_id)
    expect(run.start.source_return_id).toBe(returned.return_id)
    const config = run.start.configuration
    expect(config.provider).toBe('local-transformers')
    expect(config.model_repository).toBe('Qwen/Qwen3-VL-2B-Instruct')
    expect(config.model_revision).toBe(manifest.model_revision)
    expect(config.processor_revision).toBe(manifest.model_revision)
    expect(config.device).toBe(`cuda:${manifest.device}`)
    expect(config.preprocessing.prompt_sha256).toMatch(/^[a-f0-9]{64}$/)
    expect(config.generation.image_mode).toBe('joint')
    expect(config.generation.identity_candidates_allowed).toBe(false)
    expect(config.generation.decoding).toBe('lm-format-enforcer')
    expect(run.outcome!.metrics.schema_sha256).toBe(config.generation.schema_sha256_2)
    expect(run.outcome!.metrics.schema_version).toBe(config.generation.schema_version)
    expect(run.outcome!.metrics.decoding).toBe(config.generation.decoding)
    expect(run.outcome!.metrics.vision_forward_calls).toBe(1)
    for (const metric of ['input_tokens', 'output_tokens', 'peak_allocated_bytes', 'peak_reserved_bytes', 'inference_seconds']) {
      expect(run.outcome!.metrics[metric]).toEqual(expect.any(Number))
      expect(run.outcome!.metrics[metric]).toBeGreaterThan(0)
    }
    expect(run.outcome!.raw_output?.length).toBeGreaterThan(0)
    expect(run.outcome!.applied_event_ids.length).toBeGreaterThan(0)
    const output = run.outcome!.output!
    expect(output).not.toBeNull()
    expect(output.candidates).toEqual([])
    expect(output.uncertainties.length).toBeGreaterThan(0)
    for (const entry of [...output.observations, ...output.additional_views]) {
      expect(entry.image_indices.length).toBeGreaterThan(0)
      expect(entry.image_indices.every(index => Number.isInteger(index) && index >= 1 && index <= 2)).toBe(true)
    }
    await expect(page.locator('.inference-result').getByText('succeeded', { exact: true })).toBeVisible()
    await expect(page.getByText(/Identity unknown\. No catalog identity was proposed/)).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Model observations', exact: true })).toBeVisible()
    for (const observation of output.observations) await expect(page.getByText(observation.text, { exact: true }).first()).toBeVisible()
    for (const uncertainty of output.uncertainties) await expect(page.getByText(uncertainty, { exact: true }).first()).toBeVisible()
    await expect(page.getByRole('combobox', { name: 'Component type', exact: true })).toHaveValue('')
    await expect(page.getByRole('combobox', { name: 'Revision', exact: true })).toHaveValue('')
    await expect(page.getByRole('combobox', { name: 'Visible condition', exact: true })).toHaveValue('unknown')
    finalState = await held(request, component.physical_component_id)
    screenshots.push('desktop-product-inspection.png')
    await capture(page, screenshots.at(-1)!)
    await page.setViewportSize({ width: 390, height: 844 })
    screenshots.push('mobile-product-inspection.png')
    await capture(page, screenshots.at(-1)!)
    await page.setViewportSize({ width: 1440, height: 1000 })

    stage = 'operator rejection and additional evidence request without truth labels'
    const reason = 'Automated operator-role exercise: this unverified output is not accepted as proof of exact catalog identity or revision. Request a readable manufacturer/model/revision label close-up and connector/detail view before independent human review. No independent human ground-truth assessment was performed.'
    await page.getByLabel(/^Rejection reason/).fill(reason)
    const rejected = await postFromUI(page, page.getByRole('button', { name: 'Reject unsupported proposal', exact: true }), `/inference/${escaped(runId)}/reject`, 200)
    rejection = rejected.request().postDataJSON() as Record<string, unknown>
    expect(rejection.reason).toBe(reason)
    expect(rejection.expected_version).toBe(finalState.history.current.version)
    await expect(page.getByText(/Rejection recorded\. The original model output remains in history/)).toBeVisible()
    finalState = await held(request, component.physical_component_id)
    const event = finalState.history.events.find(item => item.event_id === rejection!.rejection_id)
    expect(event?.kind).toBe('uncertainty')
    expect(event?.payload.source).toBe('operator')
    expect(event?.payload.source_reference).toBe(manifest.operator_id)
    expect(event?.payload.reason).toContain(reason)
    expect(event?.payload.reason).toContain(runId)
    expect(await get<InferenceRun>(request, `/inference/${escaped(runId)}`)).toEqual(run)

    stage = 'duplicate additional views and API authority'
    const historyBeforeDuplicate = finalState.history
    await page.getByLabel(/^Additional component images/).setInputFiles(paths)
    await page.getByRole('button', { name: 'Upload another view', exact: true }).click()
    await expect(page.getByText(/Additional views saved for photo-demo-unit\./)).toBeVisible()
    expect(await get<ImageAsset[]>(request, `/components/${escaped(component.physical_component_id)}/images`)).toEqual(expect.arrayContaining(assets))
    expect(await get<ImageAsset[]>(request, `/components/${escaped(component.physical_component_id)}/images`)).toHaveLength(2)
    finalState = await held(request, component.physical_component_id)
    expect(finalState.history).toEqual(historyBeforeDuplicate)
    const protectedRoute = `${manifest.api_url}/components/${escaped(component.physical_component_id)}/inference`
    const forbiddenCommand = { request_id: 'unauthorized-product-inference', asset_ids: assets.map(asset => asset.asset_id), expected_version: finalState.history.current.version }
    apiChecks.unauthenticated_inference_status = (await request.post(protectedRoute, { data: forbiddenCommand })).status()
    apiChecks.viewer_inference_status = (await request.post(protectedRoute, { data: forbiddenCommand, headers: { Authorization: `Bearer ${manifest.viewer_token}` } })).status()
    expect(apiChecks.unauthenticated_inference_status).toBe(401)
    expect(apiChecks.viewer_inference_status).toBe(403)
    expect(await get<InferenceRun[]>(request, `/components/${escaped(component.physical_component_id)}/inference`)).toEqual([run])
    expect(inferencePosts).toBe(1)
    expect(pageErrors).toEqual([])
    apiChecks.original_image_hashes_match = true
    apiChecks.duplicate_views_preserve_component_and_evidence = true
    apiChecks.unverified_held_without_reservation_or_completion = true
    screenshots.push('product-review-held.png')
    await capture(page, screenshots.at(-1)!)
    await holdFinalPage(page, manifest.demo_presentation)
    passed = true
    stage = 'completed'
    persist()
    writeFileSync(join(manifest.artifacts_dir, 'acceptance-result.json'), redact(JSON.stringify({
      passed, real_product_images: true, real_inference: true, simulated_intake: true,
      browser_version: browser.version(), product_artifact: 'product-inference-results.json',
      returns: 1, physical_components: 1, managed_images: 2, inference_runs: 1, vision_forward_calls: 1,
      inference_status: run.outcome!.status, identity_candidates: 0, independent_human_review: false,
      held_components: 1, reserved_components: 0, completed_kits: 0, page_errors: pageErrors, screenshots, limitations,
      demo_presentation: manifest.demo_presentation,
    }, null, 2)), 'utf8')
  } catch (error) {
    persist()
    const detail = redact(error instanceof Error ? error.message : String(error))
    writeFileSync(join(manifest.artifacts_dir, 'acceptance-failure.json'), JSON.stringify({ passed: false, real_product_images: true, stage, error: detail, page_errors: pageErrors }, null, 2), 'utf8')
    throw new Error(`${stage}: ${detail}`)
  }
})
