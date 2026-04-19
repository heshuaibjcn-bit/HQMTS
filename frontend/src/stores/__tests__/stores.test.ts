import { describe, it, expect, vi } from 'vitest'
import { useEnvironmentStore } from '../environment-store'
import { useNotificationStore } from '../notification-store'
import { useWsStore } from '../ws-store'

describe('useEnvironmentStore', () => {
  it('starts with research environment', () => {
    expect(useEnvironmentStore.getState().currentEnv).toBe('research')
  })

  it('setEnvironment changes env', () => {
    useEnvironmentStore.getState().setEnvironment('paper')
    expect(useEnvironmentStore.getState().currentEnv).toBe('paper')
  })

  it('setEnvironment to live', () => {
    useEnvironmentStore.getState().setEnvironment('live')
    expect(useEnvironmentStore.getState().currentEnv).toBe('live')
  })
})

describe('useNotificationStore', () => {
  it('starts empty', () => {
    expect(useNotificationStore.getState().notifications).toEqual([])
  })

  it('addNotification adds a notification', () => {
    vi.useFakeTimers()
    useNotificationStore.getState().addNotification('info', 'Test message')
    const { notifications } = useNotificationStore.getState()
    expect(notifications).toHaveLength(1)
    expect(notifications[0].type).toBe('info')
    expect(notifications[0].message).toBe('Test message')
    vi.useRealTimers()
  })

  it('removeNotification removes by id', () => {
    vi.useFakeTimers()
    useNotificationStore.getState().addNotification('error', 'Error msg')
    const id = useNotificationStore.getState().notifications[0].id
    useNotificationStore.getState().removeNotification(id)
    expect(useNotificationStore.getState().notifications).toHaveLength(0)
    vi.useRealTimers()
  })

  it('auto-removes notification after 5 seconds', () => {
    vi.useFakeTimers()
    useNotificationStore.getState().addNotification('warning', 'Will disappear')
    expect(useNotificationStore.getState().notifications).toHaveLength(1)
    vi.advanceTimersByTime(5000)
    expect(useNotificationStore.getState().notifications).toHaveLength(0)
    vi.useRealTimers()
  })
})

describe('useWsStore', () => {
  it('starts disconnected', () => {
    expect(useWsStore.getState().status).toBe('disconnected')
  })

  it('setStatus updates status', () => {
    useWsStore.getState().setStatus('connected')
    expect(useWsStore.getState().status).toBe('connected')
  })

  it('tracks connecting state', () => {
    useWsStore.getState().setStatus('connecting')
    expect(useWsStore.getState().status).toBe('connecting')
  })
})
