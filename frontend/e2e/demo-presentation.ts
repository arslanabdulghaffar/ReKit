import type { Page } from '@playwright/test'

export interface DemoPresentation {
  headed: boolean
  slow_mo_ms: number
  hold_seconds: number
}

export function demoPresentation(value: unknown): DemoPresentation {
  if (value === undefined) return { headed: false, slow_mo_ms: 0, hold_seconds: 0 }
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid demo presentation settings.')
  const options = value as DemoPresentation
  if (typeof options.headed !== 'boolean'
      || !Number.isInteger(options.slow_mo_ms) || options.slow_mo_ms < 0 || options.slow_mo_ms > 500
      || !Number.isInteger(options.hold_seconds) || options.hold_seconds < 0 || options.hold_seconds > 120
      || (!options.headed && (options.slow_mo_ms > 0 || options.hold_seconds > 0))) {
    throw new Error('Demo presentation requires a headed browser for bounded pacing or final inspection.')
  }
  return options
}

export async function holdFinalPage(page: Page, value: unknown): Promise<void> {
  const options = demoPresentation(value)
  if (options.hold_seconds === 0) return
  await page.bringToFront()
  // An intentional presentation window, after all acceptance assertions pass.
  // The test owns this page and the Python runner still enforces a hard deadline.
  await page.waitForTimeout(options.hold_seconds * 1000)
}
