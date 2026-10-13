import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import type { APIRequestContext, Locator, Page, Response } from '@playwright/test'
import type {
  AuditRecord, EconomicScenario, EvidenceHistory, ImageAsset, InventorySnapshot,
  PhysicalComponent, ReturnBatch, ReturnRecord, StoredPlan, Verification,
} from '../src/types'

interface BrowserFixture {
  synthetic: true
  base_url: string
  api_url: string
  operator_token: string
  viewer_token: string
  operator_id: string
  viewer_id: string
  artifacts_dir: string
  images: Record<string, string[]>
  fixture: {
    synthetic: true
    batch: ReturnBatch
    returns: ReturnRecord[]
    components: { component: PhysicalComponent; verification: Verification }[]
    scenario: EconomicScenario
    expected: { return_count: number; physical_component_count: number; completed_kit_count: number; modeled_value_cents: number }
  }
}

const manifest = JSON.parse(readFileSync(process.env.REKIT_BROWSER_FIXTURE!, 'utf8')) as BrowserFixture
if (manifest.synthetic !== true || manifest.fixture.synthetic !== true || manifest.api_url !== 'http://127.0.0.1:8000') {
  throw new Error('Acceptance requires an isolated local synthetic backend.')
}
const fixture = manifest.fixture
const headers = { Authorization: `Bearer ${manifest.operator_token}` }
const redact = (value: string) => value.replaceAll(manifest.operator_token, '[redacted]').replaceAll(manifest.viewer_token, '[redacted]')
const path = (value: string) => encodeURIComponent(value)

async function get<T>(request: APIRequestContext, route: string): Promise<T> {
  const response = await request.get(`${manifest.api_url}${route}`, { headers })
  expect(response.status(), `GET ${route}`).toBe(200)
  return response.json() as Promise<T>
}

async function postFromUI(page: Page, button: Locator, route: string, status: number): Promise<Response> {
  const pending = page.waitForResponse(response => response.url() === `${manifest.base_url}/api${route}` && response.request().method() === 'POST')
  await button.click()
  const response = await pending
  expect(response.status(), `POST ${route}`).toBe(status)
  return response
}

async function capture(page: Page, filename: string): Promise<void> {
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: join(manifest.artifacts_dir, filename), fullPage: true, animations: 'disabled' })
}

async function login(page: Page, credential: string): Promise<void> {
  await page.goto('/')
  await expect(page.getByLabel('Operator token')).toBeVisible()
  // Credentials come from a private temporary manifest. No trace, video, or
  // automatic failure screenshot is enabled; failure messages are redacted.
  await page.getByLabel('Operator token').fill(credential)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Register batch', exact: true })).toBeVisible()
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 })
}

async function selectReview(page: Page, componentId: string, version: number): Promise<void> {
  await page.getByRole('button', { name: /02.*Component review/ }).click()
  await page.getByRole('combobox', { name: 'Component to review', exact: true }).selectOption(componentId)
  const context = page.locator('.context-line').filter({ has: page.getByText(componentId, { exact: true }) })
  await expect(context).toContainText(`Evidence version ${version}`)
  await expect(page.getByLabel('Review reason', { exact: true })).toBeVisible()
}

async function verify(page: Page, request: APIRequestContext, componentId: string, type: string, revision: string): Promise<void> {
  const before = await get<EvidenceHistory>(request, `/components/${path(componentId)}/history`)
  await selectReview(page, componentId, before.current.version)
  await page.getByRole('combobox', { name: 'Component type', exact: true }).selectOption(type)
  await page.getByRole('combobox', { name: 'Revision', exact: true }).selectOption(revision)
  await page.getByRole('combobox', { name: 'Visible condition', exact: true }).selectOption('acceptable')
  const observations = before.events.filter(event => event.kind === 'observation').map(event => event.event_id)
  expect(observations).toHaveLength(2)
  for (const id of observations) await page.locator(`input[name="observation_id"][value="${id}"]`).check()
  await page.getByLabel('Review reason', { exact: true }).fill(`Synthetic manual visible-identity review: ${type} revision ${revision}; no functional or safety claim.`)
  const response = await postFromUI(page, page.getByRole('button', { name: before.current.verification ? 'Record correction' : 'Verify component', exact: true }), `/components/${path(componentId)}/verification`, 200)
  const command = response.request().postDataJSON()
  expect(command.expected_version).toBe(before.current.version)
  expect(command.verification.supersedes_verification_id).toBe(before.current.verification?.verification_id ?? null)
  expect(command.verification).not.toHaveProperty('operator_id')
  await expect(page.getByText('Human verification recorded with its evidence links and actor identity.', { exact: true })).toBeVisible()
  const after = await get<EvidenceHistory>(request, `/components/${path(componentId)}/history`)
  expect(after.current.state).toBe('verified')
  expect(after.current.verification?.operator_id).toBe(manifest.operator_id)
  expect(after.current.verification?.identity).toEqual({ component_type_id: type, revision })
  expect(after.events).toHaveLength(before.events.length + 1)
  const check = page.waitForResponse(response => response.url().includes(`/api/components/${path(componentId)}/compatibility?`))
  await page.getByRole('button', { name: 'Check compatibility', exact: true }).click()
  const decision = await (await check).json()
  expect(decision.compatible).toBe(revision === 'A')
  await expect(page.getByText(revision === 'A' ? /Compatible under the approved policy/ : /Compatibility not established/)).toBeVisible()
}

async function generatePlan(page: Page, description: string): Promise<StoredPlan> {
  const scenario = fixture.scenario
  await page.getByRole('button', { name: /03.*Recovery planning/ }).click()
  await page.getByLabel('Scenario description', { exact: true }).fill(description)
  await page.getByRole('combobox', { name: /^Currency/ }).selectOption(scenario.currency)
  await page.getByLabel('Valuation date', { exact: true }).fill(scenario.valuation_date)
  await page.getByLabel('Labor cost per minute (cents)', { exact: true }).fill(String(scenario.labor_cost_per_minute_cents))
  await page.getByLabel(/^Labor capacity/).fill(String(scenario.labor_capacity_minutes))
  for (const kit of scenario.kits) {
    await page.getByRole('checkbox', { name: new RegExp(`Include ${kit.configuration_id}`) }).check()
    await page.getByLabel(`Selling price (cents) — ${kit.configuration_id}`, { exact: true }).fill(String(kit.selling_price_cents))
    await page.getByLabel(`Rebuild labor (minutes) — ${kit.configuration_id}`, { exact: true }).fill(String(kit.labor_minutes))
    await page.getByLabel(`Other costs (cents) — ${kit.configuration_id}`, { exact: true }).fill(String(kit.other_cost_cents))
    await page.getByLabel(`Demand limit — ${kit.configuration_id}`, { exact: true }).fill(String(kit.demand_limit))
  }
  for (const component of scenario.components) {
    const id = component.physical_component_id
    await page.getByLabel(`Donor value (cents) — ${id}`, { exact: true }).fill(String(component.donor_value_cents))
    await page.getByLabel(`Salvage value (cents) — ${id}`, { exact: true }).fill(String(component.salvage_value_cents ?? 0))
    await page.getByLabel(`Salvage labor (minutes) — ${id}`, { exact: true }).fill(String(component.salvage_labor_minutes ?? 0))
  }
  for (const returned of scenario.returns) {
    await page.getByLabel(`Liquidation value (cents) — ${returned.return_id}`, { exact: true }).fill(String(returned.liquidation_value_cents))
    await page.getByLabel(`Liquidation labor (minutes) — ${returned.return_id}`, { exact: true }).fill(String(returned.liquidation_labor_minutes ?? 0))
  }
  const response = await postFromUI(page, page.getByRole('button', { name: 'Generate recovery plan', exact: true }), '/plans', 201)
  const command = response.request().postDataJSON()
  expect(Object.keys(command).sort()).toEqual(['scenario', 'settings'])
  const stored = await response.json() as StoredPlan
  await expect(page.getByText(stored.plan.plan_id, { exact: true })).toBeVisible()
  await expect(page.getByText('Plan version 1', { exact: true })).toBeVisible()
  return stored
}

test('real images and manual review recover two kits without bypassing incompatible inventory', async ({ page, browser, request }) => {
  let stage = 'authentication'
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(redact(error.message)))
  const assets: Record<string, ImageAsset[]> = {}
  try {
    expect(await get<InventorySnapshot>(request, '/inventory')).toEqual({ items: [], completed_kits: [] })
    await login(page, manifest.operator_token)
    await expect(page.getByText(manifest.operator_id, { exact: true })).toBeVisible()
    expect((await request.get(`${manifest.api_url}/inventory`)).status()).toBe(401)

    stage = 'native batch, return, and physical intake'
    await page.getByLabel('Batch ID', { exact: true }).fill(fixture.batch.batch_id)
    expect(await page.getByLabel('Batch ID', { exact: true }).evaluate((input: HTMLInputElement) => input.checkValidity())).toBe(true)
    await postFromUI(page, page.getByRole('button', { name: 'Register batch', exact: true }), '/batches', 201)
    for (const returned of fixture.returns) {
      // Native combobox names exclude nested option text from the wrapping label.
      await page.getByRole('combobox', { name: 'Source batch', exact: true }).selectOption(returned.batch_id)
      await page.getByLabel('Return ID', { exact: true }).fill(returned.return_id)
      await page.getByRole('combobox', { name: 'Product family', exact: true }).selectOption(returned.product_family_id)
      await page.getByRole('combobox', { name: 'Declared configuration', exact: true }).selectOption(returned.declared_configuration_id!)
      await postFromUI(page, page.getByRole('button', { name: 'Register return', exact: true }), '/returns', 201)
    }
    for (const record of fixture.components) {
      await page.getByRole('combobox', { name: 'Source return', exact: true }).selectOption(record.component.source_return_id)
      await page.getByLabel(/^Physical component ID/).fill(record.component.physical_component_id)
      await postFromUI(page, page.getByRole('button', { name: 'Register component', exact: true }), '/components', 201)
    }
    expect(await get<ReturnRecord[]>(request, '/returns')).toHaveLength(3)
    expect((await get<InventorySnapshot>(request, '/inventory')).items).toHaveLength(4)

    stage = 'native image selection, duplicate handling, and invalid uploads'
    for (const record of fixture.components) {
      const id = record.component.physical_component_id
      await page.getByRole('combobox', { name: 'Component to photograph', exact: true }).selectOption(id)
      const input = page.getByLabel(/^Component images/)
      expect(await input.evaluate((element: HTMLInputElement) => element.validity.valueMissing)).toBe(true)
      await input.setInputFiles(manifest.images[id])
      expect(await input.evaluate((element: HTMLInputElement) => ({ count: element.files?.length, valid: element.checkValidity() }))).toEqual({ count: 2, valid: true })
      await page.getByRole('button', { name: 'Upload images', exact: true }).click()
      await expect(page.getByText(`Image evidence saved for ${id}. No additional physical stock was created.`, { exact: true })).toBeVisible()
      const previews = page.getByRole('img', { name: `Evidence for ${id}`, exact: true })
      await expect(previews).toHaveCount(2)
      await expect.poll(() => previews.evaluateAll(images => images.every(image => image instanceof HTMLImageElement && image.complete && image.naturalWidth > 0))).toBe(true)
      assets[id] = await get<ImageAsset[]>(request, `/components/${path(id)}/images`)
      expect(assets[id]).toHaveLength(2)
      expect(assets[id].every(asset => asset.physical_component_id === id && asset.return_id === record.component.source_return_id && asset.uploaded_by === manifest.operator_id)).toBe(true)
    }
    const first = fixture.components[0].component
    await page.getByRole('combobox', { name: 'Component to photograph', exact: true }).selectOption(first.physical_component_id)
    await page.getByLabel(/^Component images/).setInputFiles(manifest.images[first.physical_component_id][0])
    await postFromUI(page, page.getByRole('button', { name: 'Upload images', exact: true }), `/components/${path(first.physical_component_id)}/images?return_id=${path(first.source_return_id)}`, 200)
    await expect(page.getByText(/1 duplicate upload\(s\) reused existing evidence/)).toBeVisible()
    await page.getByLabel(/^Component images/).setInputFiles({ name: 'synthetic-corrupt.png', mimeType: 'image/png', buffer: Buffer.from('Synthetic invalid image bytes.') })
    await postFromUI(page, page.getByRole('button', { name: 'Upload images', exact: true }), `/components/${path(first.physical_component_id)}/images?return_id=${path(first.source_return_id)}`, 422)
    await expect(page.getByRole('alert')).toBeVisible()
    expect(await get<ImageAsset[]>(request, `/components/${path(first.physical_component_id)}/images`)).toEqual(assets[first.physical_component_id])
    expect((await get<InventorySnapshot>(request, '/inventory')).items).toHaveLength(4)
    const uploadUrl = `${manifest.api_url}/components/${path(first.physical_component_id)}/images?return_id=${path(first.source_return_id)}`
    const imageBytes = readFileSync(manifest.images[first.physical_component_id][0])
    expect((await request.post(uploadUrl, { data: imageBytes, headers: { 'Content-Type': 'image/png' } })).status()).toBe(401)
    expect((await request.post(uploadUrl, { data: imageBytes, headers: { Authorization: `Bearer ${manifest.viewer_token}`, 'Content-Type': 'image/png' } })).status()).toBe(403)
    expect(await get<ImageAsset[]>(request, `/components/${path(first.physical_component_id)}/images`)).toEqual(assets[first.physical_component_id])

    stage = 'authenticated image review and responsive screenshots'
    const initialHistory = await get<EvidenceHistory>(request, `/components/${path(first.physical_component_id)}/history`)
    expect(initialHistory.events).toHaveLength(2)
    await selectReview(page, first.physical_component_id, initialHistory.current.version)
    await expect(page.getByRole('img', { name: `Evidence for ${first.physical_component_id}`, exact: true })).toHaveCount(2)
    await capture(page, 'desktop-evidence.png')
    await page.setViewportSize({ width: 390, height: 844 })
    await capture(page, 'mobile-evidence.png')
    await page.setViewportSize({ width: 1440, height: 1000 })

    stage = 'unresolved and incompatible negative scenario'
    await verify(page, request, fixture.components[0].component.physical_component_id, 'body', 'A')
    await verify(page, request, fixture.components[1].component.physical_component_id, 'body', 'A')
    const unresolvedId = fixture.components[2].component.physical_component_id
    const incompatibleId = fixture.components[3].component.physical_component_id
    await verify(page, request, incompatibleId, 'adapter', 'B')
    expect((await get<EvidenceHistory>(request, `/components/${path(unresolvedId)}/history`)).current.state).toBe('unresolved')
    const negative = await generatePlan(page, 'Synthetic negative case: unresolved adapter and incompatible revision B.')
    expect(negative.plan.status).toBe('OPTIMAL')
    expect(negative.plan.selected_actions.some(action => action.kind === 'rebuild')).toBe(false)
    expect(negative.plan.selected_actions.find(action => action.component_ids.includes(unresolvedId))?.kind).toBe('hold')
    expect(negative.plan.rejections.some(rejection => rejection.subject.includes(unresolvedId))).toBe(true)
    expect(negative.plan.rejections.some(rejection => rejection.subject.includes(incompatibleId))).toBe(true)
    const beforeRejectedCompletion = await get<InventorySnapshot>(request, '/inventory')
    const rejectedAction = negative.plan.selected_actions[0]
    const unsupported = await request.post(`${manifest.api_url}/plans/${path(negative.plan.plan_id)}/actions/${path(rejectedAction.action_id)}/complete`, {
      headers, data: { operation_id: 'synthetic-negative-completion', expected_version: negative.version, reason: 'Synthetic forbidden completion probe.', confirmed: true, component_ids: rejectedAction.component_ids, evidence_references: ['synthetic:unsupported-action'], completed_kit_id: null },
    })
    expect(unsupported.status()).toBe(409)
    expect(await get<InventorySnapshot>(request, '/inventory')).toEqual(beforeRejectedCompletion)
    expect(await get<AuditRecord[]>(request, `/plans/${path(negative.plan.plan_id)}/audit`)).toHaveLength(1)
    await page.getByLabel('Approval or cancellation reason', { exact: true }).fill('Discard the negative synthetic proposal before correcting evidence.')
    await postFromUI(page, page.getByRole('button', { name: 'Cancel plan', exact: true }), `/plans/${path(negative.plan.plan_id)}/cancel`, 200)
    await expect(page.getByText('Plan cancelled. Unconsumed reservations released.', { exact: true })).toBeVisible()

    stage = 'manual correction and real CPU optimization'
    await verify(page, request, unresolvedId, 'adapter', 'A')
    await verify(page, request, incompatibleId, 'adapter', 'A')
    const corrected = await get<EvidenceHistory>(request, `/components/${path(incompatibleId)}/history`)
    expect(corrected.events.filter(event => event.kind === 'verification')).toHaveLength(2)
    const proposal = await generatePlan(page, 'Synthetic three-return recovery: explicit costs, two operator-confirmed kits.')
    expect(proposal.plan.status).toBe('OPTIMAL')
    expect(proposal.plan.solver_version).toBeTruthy()
    expect(proposal.plan.selected_actions).toHaveLength(2)
    expect(proposal.plan.selected_actions.every(action => action.kind === 'rebuild')).toBe(true)
    expect(proposal.plan.modeled_value_cents).toBe(17500)
    expect(proposal.plan.cash_recovery_cents).toBe(17500)
    expect(proposal.plan.retained_value_cents).toBe(0)
    expect(proposal.plan.labor_minutes).toBe(60)
    await expect(page.getByText('USD 175.00', { exact: true }).first()).toBeVisible()
    await capture(page, 'plan-overview.png')
    const beforeApproval = await get<InventorySnapshot>(request, '/inventory')
    expect(beforeApproval.completed_kits).toHaveLength(0)
    expect(beforeApproval.items.every(entry => entry.availability === 'available')).toBe(true)
    const firstAction = proposal.plan.selected_actions[0]
    const premature = await request.post(`${manifest.api_url}/plans/${path(proposal.plan.plan_id)}/actions/${path(firstAction.action_id)}/complete`, {
      headers, data: { operation_id: 'synthetic-unreserved-completion', expected_version: proposal.version, reason: 'Synthetic unreserved completion probe.', confirmed: true, component_ids: firstAction.component_ids, evidence_references: ['synthetic:premature-completion'], completed_kit_id: 'synthetic-premature-kit' },
    })
    expect(premature.status()).toBe(409)
    expect(await get<InventorySnapshot>(request, '/inventory')).toEqual(beforeApproval)

    stage = 'atomic approval and reservation'
    await page.getByLabel('Approval or cancellation reason', { exact: true }).fill('Synthetic operator reviewed compatibility, economics, and every physical allocation.')
    const approval = await postFromUI(page, page.getByRole('button', { name: 'Approve and reserve', exact: true }), `/plans/${path(proposal.plan.plan_id)}/approve`, 200)
    expect(approval.request().postDataJSON()).not.toHaveProperty('operator_id')
    await expect(page.getByText('Plan version 2', { exact: true })).toBeVisible()
    const reserved = await get<InventorySnapshot>(request, '/inventory')
    expect(reserved.items).toHaveLength(4)
    expect(reserved.items.every(entry => entry.availability === 'reserved' && entry.plan_id === proposal.plan.plan_id)).toBe(true)
    expect(reserved.completed_kits).toHaveLength(0)
    await capture(page, 'reserved-plan.png')

    stage = 'explicit physical completion and lineage'
    let firstCompletion: { route: string; body: object } | undefined
    for (const [index, action] of proposal.plan.selected_actions.entries()) {
      const card = page.locator('article.action-card').filter({ has: page.getByText(action.component_ids[0], { exact: true }) })
      await card.getByText('Confirm kit rebuild completion', { exact: true }).click()
      const completeButton = card.getByRole('button', { name: 'Record completion', exact: true })
      await expect(completeButton).toBeDisabled()
      for (const id of action.component_ids) await card.getByRole('checkbox', { name: `I checked physical component ${id}`, exact: true }).check()
      await card.getByLabel('Completed kit ID', { exact: true }).fill(`synthetic-browser-kit-${index + 1}`)
      await card.getByLabel(/^Completion evidence references/).fill(action.component_ids.map(id => `asset:${assets[id][0].asset_id}`).join('\n'))
      await card.getByLabel('Completion reason', { exact: true }).fill('Synthetic explicit confirmation of the reserved physical identities; no safety certification.')
      await expect(completeButton).toBeDisabled()
      await card.getByRole('checkbox', { name: 'I confirm this physical action is complete.', exact: true }).check()
      const route = `/plans/${path(proposal.plan.plan_id)}/actions/${path(action.action_id)}/complete`
      const completion = await postFromUI(page, completeButton, route, 200)
      const command = completion.request().postDataJSON()
      expect(command).not.toHaveProperty('operator_id')
      expect(command.confirmed).toBe(true)
      expect(command.component_ids).toEqual(action.component_ids)
      expect(command.expected_version).toBe(index + 2)
      if (!firstCompletion) firstCompletion = { route, body: command }
      await expect(page.getByText(`Plan version ${index + 3}`, { exact: true })).toBeVisible()
      const checkpoint = await get<InventorySnapshot>(request, '/inventory')
      expect(checkpoint.completed_kits).toHaveLength(index + 1)
      expect(checkpoint.items.filter(entry => entry.availability === 'consumed')).toHaveLength((index + 1) * 2)
    }
    const final = await get<InventorySnapshot>(request, '/inventory')
    expect(final.items).toHaveLength(4)
    expect(final.items.every(entry => entry.availability === 'consumed')).toBe(true)
    expect(final.completed_kits).toHaveLength(2)
    const lineage = final.completed_kits.flatMap(kit => kit.component_ids)
    expect(new Set(lineage).size).toBe(4)
    expect(lineage.sort()).toEqual(fixture.components.map(record => record.component.physical_component_id).sort())
    expect(final.completed_kits.every(kit => kit.operator_id === manifest.operator_id && kit.plan_id === proposal.plan.plan_id && kit.evidence_references.length === 2)).toBe(true)
    const retry = await request.post(`${manifest.api_url}${firstCompletion!.route}`, { headers, data: firstCompletion!.body })
    expect(retry.status()).toBe(200)
    expect(await get<InventorySnapshot>(request, '/inventory')).toEqual(final)
    const audit = await get<AuditRecord[]>(request, `/plans/${path(proposal.plan.plan_id)}/audit`)
    expect(audit.map(record => record.kind)).toEqual(['proposed', 'approved', 'action_completed', 'action_completed'])
    expect(audit.every(record => record.operator_id === manifest.operator_id)).toBe(true)
    expect((await get<StoredPlan>(request, `/plans/${path(proposal.plan.plan_id)}`)).state).toBe('completed')
    await expect(page.locator('.audit-list > li')).toHaveCount(4)
    await page.getByRole('button', { name: /05.*Inventory/ }).click()
    await expect(page.getByRole('heading', { name: 'synthetic-browser-kit-1', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'synthetic-browser-kit-2', exact: true })).toBeVisible()
    await capture(page, 'final-inventory.png')

    stage = 'viewer authority and final browser checks'
    const viewer = await browser.newPage({ baseURL: manifest.base_url })
    viewer.on('pageerror', error => pageErrors.push(redact(error.message)))
    try {
      await login(viewer, manifest.viewer_token)
      await expect(viewer.getByRole('button', { name: 'Register batch', exact: true })).toBeDisabled()
      await expect(viewer.getByRole('button', { name: 'Register component', exact: true })).toBeDisabled()
      await viewer.getByRole('button', { name: /03.*Recovery planning/ }).click()
      await expect(viewer.getByRole('button', { name: 'Generate recovery plan', exact: true })).toBeDisabled()
    } finally { await viewer.close() }
    expect(pageErrors).toEqual([])
    writeFileSync(join(manifest.artifacts_dir, 'acceptance-result.json'), JSON.stringify({
      synthetic: true, passed: true, browser_version: browser.version(), page_errors: pageErrors,
      returns: 3, physical_components: 4, managed_images: Object.values(assets).flat().length,
      native_multi_file_validation: true, duplicate_upload_status: 200, invalid_upload_status: 422,
      unauthenticated_upload_status: 401, viewer_upload_status: 403,
      negative_plan_id: negative.plan.plan_id, negative_rebuilds: 0, rejected_completion_statuses: [409, 409],
      recovery_plan_id: proposal.plan.plan_id, solver_status: proposal.plan.status, solver_version: proposal.plan.solver_version,
      modeled_value_cents: proposal.plan.modeled_value_cents, cash_recovery_cents: proposal.plan.cash_recovery_cents,
      retained_value_cents: proposal.plan.retained_value_cents, reserved_before_completion: 4,
      completed_kits: 2, consumed_components: 4, audit_events: audit.length, completion_retry_status: 200,
      screenshots: ['desktop-evidence.png', 'mobile-evidence.png', 'plan-overview.png', 'reserved-plan.png', 'final-inventory.png'],
    }, null, 2), 'utf8')
  } catch (error) {
    const detail = redact(error instanceof Error ? error.message : String(error))
    writeFileSync(join(manifest.artifacts_dir, 'acceptance-failure.json'), JSON.stringify({ synthetic: true, passed: false, stage, error: detail, page_errors: pageErrors }, null, 2), 'utf8')
    throw new Error(`${stage}: ${detail}`)
  }
})
