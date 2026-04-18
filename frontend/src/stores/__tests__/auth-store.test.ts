import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuthStore } from '../auth-store'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('useAuthStore', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    useAuthStore.setState({
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      user: null,
    })
  })

  it('starts unauthenticated', () => {
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
  })

  it('login succeeds with valid credentials', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'at', refresh_token: 'rt' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ user_id: 'u1', username: 'test', role: 'trader', display_name: 'Test' }),
      })

    await useAuthStore.getState().login('test', 'pass')
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.token).toBe('at')
    expect(state.user?.username).toBe('test')
  })

  it('login throws on invalid credentials', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    })
    await expect(useAuthStore.getState().login('bad', 'pass')).rejects.toThrow('Invalid credentials')
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('setTokens updates token state', () => {
    useAuthStore.getState().setTokens('new-at', 'new-rt')
    expect(useAuthStore.getState().token).toBe('new-at')
    expect(useAuthStore.getState().refreshToken).toBe('new-rt')
  })

  it('logout clears state', async () => {
    useAuthStore.setState({
      token: 'at',
      refreshToken: 'rt',
      isAuthenticated: true,
      user: { user_id: 'u1', username: 'test', role: 'trader', display_name: 'T' },
    })
    mockFetch.mockResolvedValueOnce({ ok: true })

    await useAuthStore.getState().logout()
    const state = useAuthStore.getState()
    expect(state.token).toBeNull()
    expect(state.isAuthenticated).toBe(false)
    expect(state.user).toBeNull()
  })

  it('checkAuth with valid token sets user', async () => {
    useAuthStore.setState({ token: 'valid' })
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ user_id: 'u1', username: 'test', role: 'trader', display_name: 'Test' }),
    })

    await useAuthStore.getState().checkAuth()
    expect(useAuthStore.getState().user?.username).toBe('test')
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it('checkAuth with expired token tries refresh', async () => {
    useAuthStore.setState({ token: 'expired', refreshToken: 'valid-refresh' })
    mockFetch
      // First /auth/me: 401
      .mockResolvedValueOnce({ ok: false, status: 401 })
      // Refresh: success
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'new-at', refresh_token: 'new-rt' }),
      })
      // Retry /auth/me: success
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ user_id: 'u1', username: 'test', role: 'trader', display_name: 'Test' }),
      })

    await useAuthStore.getState().checkAuth()
    expect(useAuthStore.getState().token).toBe('new-at')
    expect(useAuthStore.getState().user?.username).toBe('test')
  })

  it('checkAuth with no token clears state', async () => {
    useAuthStore.setState({ token: null })
    await useAuthStore.getState().checkAuth()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().user).toBeNull()
  })
})
