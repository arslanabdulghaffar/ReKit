import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { defineConfig } from '@playwright/test'

const fixturePath = process.env.REKIT_BROWSER_FIXTURE
if (!fixturePath) throw new Error('Run evaluation/run_browser_acceptance.py to create isolated browser fixtures.')
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8')) as { base_url: string; artifacts_dir: string; synthetic: boolean; real_inference?: boolean }
if (fixture.synthetic !== true || fixture.base_url !== 'http://127.0.0.1:5173') {
  throw new Error('Browser acceptance requires the local synthetic runner.')
}
const executablePath = [
  process.env.REKIT_BROWSER_EXECUTABLE,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find((candidate): candidate is string => Boolean(candidate && existsSync(candidate)))
if (!executablePath) throw new Error('An installed Chrome or Edge browser is required; no browser is downloaded.')

export default defineConfig({
  testDir: './e2e',
  testMatch: 'recovery.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: fixture.real_inference === true ? 600_000 : 180_000,
  expect: { timeout: 10_000 },
  reporter: 'line',
  outputDir: join(fixture.artifacts_dir, 'playwright-output'),
  preserveOutput: 'never',
  use: {
    browserName: 'chromium',
    baseURL: fixture.base_url,
    viewport: { width: 1440, height: 1000 },
    headless: true,
    launchOptions: { executablePath },
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
})
