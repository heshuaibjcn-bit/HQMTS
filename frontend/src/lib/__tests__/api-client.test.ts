import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuthStore } from '@/stores/auth-store'

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// Import after mocking
const { apiClient } = await import('../api-client')

describe('ApiClient', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    useAuthStore.setState({
      token: 'test-access-token',
      refreshToken: 'test-refresh-token',
      isAuthenticated: true,
      user: null,
    })
  })

  it('injects Bearer token into requests', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: 'ok' }),
    })
    await apiClient.get('/test')
    const call = mockFetch.mock.calls[0]
    expect(call[1].headers['Authorization']).toBe('Bearer test-access-token')
  })

  it('returns parsed JSON for successful responses', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ orders: [] }),
    })
    const result = await apiClient.get('/orders')
    expect(result).toEqual({ orders: [] })
  })

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ detail: 'Server error' }),
    })
    await expect(apiClient.get('/test')).rejects.toThrow('Server error')
  })

  it('returns undefined for 204 responses', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
    })
    const result = await apiClient.delete('/test/123')
    expect(result).toBeUndefined()
  })

  it('attempts token refresh on 401', async () => {
    // First call: 401
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
    })
    // Refresh call: success
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ access_token: 'new-token', refresh_token: 'new-refresh' }),
    })
    // Retry call: success
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: 'refreshed' }),
    })

    const result = await apiClient.get('/test')
    expect(result).toEqual({ data: 'refreshed' })
    expect(useAuthStore.getState().token).toBe('new-token')
  })

  it('calls logout when refresh fails on 401', async () => {
    useAuthStore.setState({ token: 'expired', refreshToken: 'expired-refresh' })

    // First call: 401
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
    })
    // Refresh call: fail
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
    })

    await expect(apiClient.get('/test')).rejects.toThrow('Session expired')
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('concurrent 401s share single refresh promise', async () => {
    let refreshCallCount = 0

    // 401 response
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
    })
    // Refresh call
    mockFetch.mockImplementationOnce(async () => {
      refreshCallCount++
      return { ok: true, json: () => Promise.resolve({ access_token: 'new', refresh_token: 'new' }) }
    })
    // Retry after refresh
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ok: true }),
    })

    await apiClient.get('/test')
    expect(refreshCallCount).toBe(1)
  })

  it('appends query params for GET requests', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    })
    await apiClient.get('/orders', { status: 'pending' })
    expect(mockFetch.mock.calls[0][0]).toContain('status=pending')
  })
})
