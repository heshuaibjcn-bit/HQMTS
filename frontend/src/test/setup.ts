import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

// Mock sessionStorage for Zustand persist
const sessionStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
    get length() { return Object.keys(store).length },
    key: (i: number) => Object.keys(store)[i] ?? null,
  }
})()
Object.defineProperty(window, 'sessionStorage', { value: sessionStorageMock })

// Reset all Zustand stores between tests
import { useAuthStore } from '@/stores/auth-store'
import { useEnvironmentStore } from '@/stores/environment-store'
import { useNotificationStore } from '@/stores/notification-store'
import { useWsStore } from '@/stores/ws-store'

afterEach(() => {
  useAuthStore.setState({
    token: null,
    refreshToken: null,
    isAuthenticated: false,
    user: null,
  })
  useEnvironmentStore.setState({ currentEnv: 'research' })
  useNotificationStore.setState({ notifications: [] })
  useWsStore.setState({ status: 'disconnected' })
})
