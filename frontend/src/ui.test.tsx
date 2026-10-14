import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClient } from './api'
import type { ImageAsset } from './types'
import { AssetPreview } from './ui'

const originalCreate = URL.createObjectURL
const originalRevoke = URL.revokeObjectURL
beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:controlled-preview')
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => {
  URL.createObjectURL = originalCreate
  URL.revokeObjectURL = originalRevoke
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const sampleAsset: ImageAsset = {
  asset_id: 'controlled-asset', physical_component_id: 'controlled-physical-item', return_id: 'controlled-return',
  sha256: 'a'.repeat(64), byte_size: 50, media_type: 'image/png', width: 24, height: 18,
  received_at: '2026-10-13T00:00:00Z', uploaded_by: 'controlled-operator',
  observation_id: 'controlled-observation', availability: 'available',
}

it('shows loading and a readable view label while keeping exact source identity in provenance', async () => {
  let resolve!: (response: Response) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => { resolve = done })))
  render(<AssetPreview asset={sampleAsset} api={new ApiClient('controlled-memory-token')} label="Image 1" />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading original image')
  expect(document.querySelector('.asset-image')).toHaveAttribute('aria-busy', 'true')
  expect(screen.getByText('Image 1')).toBeInTheDocument()
  expect(screen.getByText(sampleAsset.asset_id).closest('details')).toBeInTheDocument()
  expect(screen.getByText(`SHA-256 ${sampleAsset.sha256}`)).toBeInTheDocument()
  await act(async () => { resolve(new Response('controlled-bytes', { headers: { 'Content-Type': 'image/png' } })) })
  const image = await screen.findByRole('img', { name: 'Image 1: evidence for controlled-physical-item' })
  fireEvent.load(image)
  expect(document.querySelector('.asset-image')).toHaveAttribute('aria-busy', 'false')
})

it('reports a browser decode failure instead of leaving a broken image or endless loading state', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('controlled-invalid-image', { headers: { 'Content-Type': 'image/png' } })))
  render(<AssetPreview asset={sampleAsset} api={new ApiClient('controlled-memory-token')} label="Image 2" />)
  fireEvent.error(await screen.findByRole('img', { name: 'Image 2: evidence for controlled-physical-item' }))
  expect(screen.getByRole('alert')).toHaveTextContent('This image could not be displayed. Reload the component or request another view.')
  expect(document.querySelector('.asset-image')).toHaveAttribute('aria-busy', 'false')
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})

it('does not fetch missing evidence and gives an explicit next step', () => {
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  render(<AssetPreview asset={{ ...sampleAsset, availability: 'missing' }} api={new ApiClient('controlled-memory-token')} label="Image 1" />)
  expect(screen.getByRole('status')).toHaveTextContent('Image missing. Restore the original evidence before reviewing this view.')
  expect(fetch).not.toHaveBeenCalled()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
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
