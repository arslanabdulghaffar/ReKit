import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClient } from './api'
import type { ImageAsset } from './types'
import { AssetPreview } from './ui'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it('revokes authenticated image blob URLs when the evidence changes or the preview unmounts', async () => {
  const create = vi.fn().mockReturnValueOnce('blob:private-first-image').mockReturnValueOnce('blob:private-second-image')
  const revoke = vi.fn()
  const originalCreate = URL.createObjectURL
  const originalRevoke = URL.revokeObjectURL
  URL.createObjectURL = create
  URL.revokeObjectURL = revoke
  vi.stubGlobal('fetch', vi.fn(async () => new Response('image', { headers: { 'Content-Type': 'image/png' } })))
  const asset: ImageAsset = {
    asset_id: 'asset-first', physical_component_id: 'physical-first', return_id: 'return-first',
    sha256: 'a'.repeat(64), byte_size: 5, media_type: 'image/png', width: 1, height: 1,
    received_at: '2026-10-13T00:00:00Z', uploaded_by: 'synthetic-reviewer',
    observation_id: 'observation-first', availability: 'available',
  }
  const api = new ApiClient('memory-only-token')
  try {
    const rendered = render(<AssetPreview asset={asset} api={api} />)
    expect(await screen.findByRole('img', { name: 'Evidence for physical-first' })).toHaveAttribute('src', 'blob:private-first-image')
    rendered.rerender(<AssetPreview asset={{ ...asset, asset_id: 'asset-second', physical_component_id: 'physical-second' }} api={api} />)
    expect(await screen.findByRole('img', { name: 'Evidence for physical-second' })).toHaveAttribute('src', 'blob:private-second-image')
    await waitFor(() => expect(revoke).toHaveBeenCalledWith('blob:private-first-image'))
    rendered.unmount()
    expect(revoke).toHaveBeenCalledWith('blob:private-second-image')
  } finally {
    URL.createObjectURL = originalCreate
    URL.revokeObjectURL = originalRevoke
  }
})
