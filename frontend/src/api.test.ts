import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError } from './api'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('authenticated API transport', () => {
  it('sends bearer credentials only through a fixed same-origin API with cookies and redirects disabled', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{}'))
    vi.stubGlobal('fetch', fetch)
    const api = new ApiClient('in-memory-token')
    await api.post('/plans/plan-1/approve', { operation_id: 'approval-1', expected_version: 2, reason: 'Reviewed.' })
    expect(fetch).toHaveBeenCalledWith('/api/plans/plan-1/approve', expect.objectContaining({
      method: 'POST', cache: 'no-store', credentials: 'omit', redirect: 'error',
      headers: { Authorization: 'Bearer in-memory-token', 'Content-Type': 'application/json' },
    }))
    const request = fetch.mock.calls[0][1] as RequestInit
    expect(JSON.parse(String(request.body))).toEqual({ operation_id: 'approval-1', expected_version: 2, reason: 'Reviewed.' })
    expect(String(request.body)).not.toContain('operator_id')
  })

  it('rejects external and escaping paths before issuing any credential-bearing request', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    const api = new ApiClient('in-memory-token')
    for (const path of ['https://outside.example/auth/me', '//outside.example/auth/me', '/../auth/me', '/%2e%2e/auth/me', '/%2e./auth/me', '/%2f%2foutside.example', '/auth\\me']) {
      await expect(api.get(path)).rejects.toThrow('Invalid API path')
    }
    expect(fetch).not.toHaveBeenCalled()
  })

  it('clears its credential and notifies the workspace when a credential is rejected', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response('{"detail":"Credential revoked."}', { status: 401 }))
      .mockResolvedValueOnce(new Response('{}'))
    vi.stubGlobal('fetch', fetch)
    const expire = vi.fn()
    const api = new ApiClient('in-memory-token', expire)
    await expect(api.get('/inventory')).rejects.toEqual(new ApiError(401, 'Credential revoked.'))
    expect(expire).toHaveBeenCalledOnce()
    await api.get('/auth/me')
    expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer ')
  })

  it('sends image uploads as raw bytes with their media type instead of JSON or multipart', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{}'))
    vi.stubGlobal('fetch', fetch)
    const file = new File(['synthetic-image-bytes'], 'close-up.png', { type: 'image/png' })
    await new ApiClient('in-memory-token').post('/components/physical-1/images?return_id=return-1', file)
    const [path, request] = fetch.mock.calls[0]
    expect(path).toBe('/api/components/physical-1/images?return_id=return-1')
    expect(request.body).toBe(file)
    expect(request.headers['Content-Type']).toBe('image/png')
  })

  it('rejects HTML returned from an image endpoint instead of creating an image preview', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>not an image</html>', {
      headers: { 'Content-Type': 'text/html' },
    })))
    await expect(new ApiClient('in-memory-token').image('/assets/image-1/content')).rejects.toEqual(
      new ApiError(422, 'The server returned an unsupported image response.'),
    )
  })
})
