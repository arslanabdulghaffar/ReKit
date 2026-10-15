/** Browser acceptance for the standalone recorded-evidence package.
 * Uses the installed browser/Playwright; never starts ReKit or a network server.
 */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, realpathSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(join(root, 'frontend/package.json'));
const { chromium } = require('playwright');
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const sourceName = 'var/mission06-offline/block-d-canonical-sensitivity-20261015-224735/receipt.json';
const sourceHash = 'cb565d5cdf87a46aa68bc02f3fe4b34da619c9d45d54c8304c63faf787a4ee3f';
const [packageArg, outputArg, ...extra] = process.argv.slice(2);
assert(packageArg && outputArg && extra.length === 0,
  'Usage: node evaluation/check_decision_evidence_demo.mjs PACKAGE NEW_QA_DIRECTORY');

function unlinked(path) {
  let current = resolve(path);
  while (true) {
    if (existsSync(current)) assert(!lstatSync(current).isSymbolicLink(), 'Refuse linked path');
    const parent = dirname(current);
    if (parent === current) break;
    current = parent;
  }
}
function within(path, parent) {
  const tail = relative(parent, path);
  return tail !== '' && tail !== '..' && !tail.startsWith(`..${sep}`) && !isAbsolute(tail);
}
const packagePath = resolve(packageArg);
const outputPath = resolve(outputArg);
const allowed = resolve(root, 'var/mission06-offline');
unlinked(packagePath); unlinked(outputPath); unlinked(allowed);
assert(within(packagePath, allowed) && within(outputPath, allowed), 'Paths must stay under offline artifacts');
assert(!within(outputPath, packagePath) && outputPath !== packagePath, 'QA must not modify the frozen package');
assert(!existsSync(outputPath), 'Refuse to replace prior QA');
assert(realpathSync(packagePath) === packagePath, 'Package must not resolve elsewhere');

// Authenticate all copied sources and renderer output before opening a browser.
const python = join(root, '.venv', 'Scripts', 'python.exe');
const check = execFileSync(python, ['-B', 'evaluation/build_decision_evidence_demo.py', '--check', packagePath],
  { cwd: root, encoding: 'utf8', timeout: 30_000 });
assert.equal(JSON.parse(check).status, 'passed');
const original = readFileSync(join(root, sourceName));
assert.equal(hash(original), sourceHash);
const source = JSON.parse(original);

function snapshot(directory) {
  const files = {};
  function walk(current) {
    for (const item of readdirSync(current, { withFileTypes: true })) {
      const path = join(current, item.name);
      unlinked(path);
      if (item.isDirectory()) walk(path);
      else if (item.isFile()) files[relative(directory, path).replaceAll('\\', '/')] = hash(readFileSync(path));
    }
  }
  walk(directory);
  return files;
}
const before = snapshot(packagePath);
const executablePath = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync);
assert(executablePath, 'Installed Chrome or Edge required; no download occurs');
mkdirSync(outputPath, { recursive: false });
const receipt = {
  status: 'running', started_at: new Date().toISOString(),
  package: relative(root, packagePath).replaceAll('\\', '/'),
  package_hashes_before: before, source_sha256: sourceHash,
  new_inference_requests: 0, new_solver_calls: 0, application_started: false,
  viewports: [], screenshots: [], page_errors: [], forbidden_requests: [], storage_calls: [],
  human_assessments_created: 0,
};
let browser;
try {
  browser = await chromium.launch({ executablePath, headless: true });
  receipt.browser_version = browser.version();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, serviceWorkers: 'block' });
  await context.route('**/*', async (route) => {
    const url = route.request().url();
    let local = false;
    if (url.startsWith('file:')) {
      const target = resolve(fileURLToPath(url));
      local = within(target, packagePath);
    }
    if (local) await route.continue();
    else { receipt.forbidden_requests.push({ method: route.request().method(), url_scheme: new URL(url).protocol }); await route.abort(); }
  });
  await context.addInitScript(() => {
    window.__rekitStorageCalls = [];
    for (const name of ['setItem', 'removeItem', 'clear']) {
      Storage.prototype[name] = function () {
        window.__rekitStorageCalls.push(name);
        throw new Error('Browser acceptance forbids storage mutation');
      };
    }
  });
  const page = await context.newPage();
  page.on('pageerror', (error) => receipt.page_errors.push(error.message));
  page.on('request', (request) => {
    if (/^https?:/i.test(request.url())) {
      receipt.forbidden_requests.push({ method: request.method(), url_scheme: new URL(request.url()).protocol });
    }
  });
  const mainUrl = pathToFileURL(join(packagePath, 'index.html')).href;
  async function capture(name, locator = null) {
    // Full-element scrolling can move sticky controls across tall mobile cards.
    // Capture in document coordinates from the top so evidence remains readable.
    await page.evaluate(() => window.scrollTo(0, 0));
    if (locator) {
      const clip = await locator.boundingBox();
      assert(clip, 'Capture target must be visible');
      await page.screenshot({ path: join(outputPath, name), fullPage: true, clip });
    } else await page.screenshot({ path: join(outputPath, name), fullPage: true });
    receipt.screenshots.push(name);
  }
  async function noOverflow() {
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'Document overflow');
  }
  async function verifyRate(rate) {
    const button = page.locator(`#labor-${rate}`);
    await button.click();
    assert.equal(await button.getAttribute('aria-pressed'), 'true');
    const panel = page.locator(`#rate-panel-${rate}`);
    assert(await panel.isVisible());
    assert(!(await page.locator(`#rate-panel-${rate === 25 ? 200 : 25}`).isVisible()));
    const rows = source.conditional_evidence_research.runs.filter((row) => row.labor_cost_per_minute_cents === rate);
    for (const row of rows) {
      const card = panel.locator(`.state-card[data-state="${row.branch}"]`);
      for (const [attribute, field] of [['total', 'modeled_value_cents'], ['cash', 'cash_recovery_cents'], ['retained', 'retained_value_cents']]) {
        assert.equal(Number(await card.locator(`[data-${attribute}-cents]`).getAttribute(`data-${attribute}-cents`)), row.plan[field]);
        assert((await card.locator(`[data-${attribute}-cents]`).innerText()).includes((row.plan[field] / 100).toFixed(2)));
      }
      const details = card.locator('details');
      await details.locator('summary').click();
      const proof = await details.innerText();
      assert(proof.includes(row.plan.input_hash) && proof.includes('OPTIMAL') && proof.includes('gap $0.00'));
      await details.locator('summary').click();
    }
    assert((await panel.locator('[data-state="review_required_held"]').innerText()).includes('hold'));
    if (rate === 200) {
      assert((await panel.locator('.conclusion').innerText()).includes('same best decision'));
    }
    await noOverflow();
  }
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: width === 1440 ? 1100 : 900 });
    await page.goto(mainUrl);
    assert.equal(await page.locator('form,input,textarea,select').count(), 0, 'No editable facts or workflow controls');
    assert.equal(await page.locator('button').count(), 2, 'Only two recorded-rate controls');
    assert((await page.locator('#comparison').innerText()).includes('Synthetic recorded scenarios'));
    await page.locator('#original-evidence summary').click();
    assert.equal(await page.locator('#original-evidence img').count(), 3);
    await page.waitForFunction(() => [...document.querySelectorAll('#original-evidence img')].every((img) => img.complete));
    assert(await page.locator('#original-evidence img').evaluateAll((images) => images.every((img) => img.complete && img.naturalWidth === 720)));
    await page.locator('#original-evidence summary').click();
    for (const rate of [25, 200]) {
      await verifyRate(rate);
      await capture(`comparison-${width}-${rate}.png`, page.locator('#comparison'));
      if (width === 320) {
        for (const state of ['historical_scripted_B', 'review_required_held', 'corrected_scripted_A']) {
          await capture(`card-${width}-${rate}-${state}.png`,
            page.locator(`#rate-panel-${rate} .state-card[data-state="${state}"]`));
        }
      }
    }
    await page.locator('#labor-25').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#labor-25').getAttribute('aria-pressed'), 'true');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'labor-200');
    await page.keyboard.press('Space');
    assert.equal(await page.locator('#labor-200').getAttribute('aria-pressed'), 'true');
    assert((await page.locator('#comparison-status').innerText()).includes('$2.00'));
    if (width === 1440) {
      await capture('main-full-desktop.png');
      await page.locator('#original-evidence summary').click();
      await capture('originals-desktop.png', page.locator('#original-evidence'));
      await page.locator('#source-proof summary').click();
      await capture('source-proof-desktop.png', page.locator('#source-proof'));
    }
    receipt.storage_calls.push(...await page.evaluate(() => window.__rekitStorageCalls));
    await page.locator('#sensitivity-link').click();
    assert(page.url().endsWith('/sensitivity.html'));
    for (const rate of [169, 170, 171]) {
      const card = page.locator(`.frontier-card[data-rate="${rate}"]`);
      const text = await card.innerText();
      assert(text.includes(`$${(rate / 100).toFixed(2)}`));
      assert(text.includes(`$${((19000 - 60 * rate) / 100).toFixed(2)}`));
      assert(text.includes(`$${((10500 - 10 * rate) / 100).toFixed(2)}`));
    }
    assert((await page.locator('.frontier-card[data-rate="170"]').innerText()).includes('3 optimal physical allocations'));
    await noOverflow();
    await capture(`sensitivity-${width}.png`);
    receipt.storage_calls.push(...await page.evaluate(() => window.__rekitStorageCalls));
    receipt.viewports.push({ width, rates_checked: [25, 200], keyboard_checked: true, original_images_loaded: 3, document_overflow: false, sensitivity_checked: true });
  }
  assert.equal(receipt.page_errors.length, 0);
  assert.equal(receipt.forbidden_requests.length, 0);
  assert.equal(receipt.storage_calls.length, 0);
  assert.deepEqual(snapshot(packagePath), before, 'Frozen package changed during review');
  receipt.package_unchanged = true;
  receipt.status = 'passed';
} catch (error) {
  receipt.status = 'failed';
  receipt.error = error.message;
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  receipt.finished_at = new Date().toISOString();
  writeFileSync(join(outputPath, 'browser-acceptance.json'), `${JSON.stringify(receipt, null, 2)}\n`, { flag: 'wx' });
}
console.log(JSON.stringify({ status: receipt.status, output: outputPath, screenshots: receipt.screenshots.length,
  page_errors: receipt.page_errors.length, forbidden_requests: receipt.forbidden_requests.length,
  error: receipt.error ?? null }));
