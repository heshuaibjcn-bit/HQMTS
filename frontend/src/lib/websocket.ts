import { useAuthStore } from '@/stores/auth-store'

type WsEventType =
  | 'signal_new'
  | 'order_update'
  | 'position_update'
  | 'risk_change'
  | 'alert'
  | 'agent_task_update'

type WsMessage = {
  type: WsEventType
  data: unknown
  event_id: string
  sequence: number
  timestamp: string
}

type EventHandler = (msg: WsMessage) => void

const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30_000
const PING_INTERVAL_MS = 30_000
const PONG_TIMEOUT_MS = 60_000

class WebSocketManager {
  private ws: WebSocket | null = null
  private handlers = new Map<string, Set<EventHandler>>()
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private pongTimer: ReturnType<typeof setTimeout> | null = null
  private lastSequence: number | null = null
  private _status: 'connecting' | 'connected' | 'disconnected' = 'disconnected'
  private statusListeners = new Set<(status: string) => void>()
  private intentionalClose = false

  get status() {
    return this._status
  }

  private setStatus(status: 'connecting' | 'connected' | 'disconnected') {
    this._status = status
    this.statusListeners.forEach((fn) => fn(status))
  }

  onStatusChange(fn: (status: string) => void) {
    this.statusListeners.add(fn)
    return () => this.statusListeners.delete(fn)
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    this.intentionalClose = false

    // H-2: Always get fresh token on connect (may have refreshed since last connect)
    const token = useAuthStore.getState().token
    if (!token) return

    this.setStatus('connecting')

    const protocol = `bearer, ${token}`
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${
      window.location.host
    }/ws`

    this.ws = new WebSocket(wsUrl, protocol)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.setStatus('connected')
      this.startPing()
    }

    this.ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)

        // Only reset pong timer on actual pong, not every message (M-1)
        if ((msg as { type: string }).type === 'pong') {
          this.resetPongTimeout()
          return
        }
        if (msg.sequence != null) {
          this.lastSequence = msg.sequence
        }

        const handlers = this.handlers.get(msg.type)
        if (handlers) {
          handlers.forEach((fn) => fn(msg))
        }
      } catch {
        // ignore malformed messages
      }
    }

    this.ws.onclose = () => {
      this.stopPing()
      this.setStatus('disconnected')
      if (!this.intentionalClose) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      // onclose will fire after onerror
    }
  }

  disconnect() {
    this.intentionalClose = true
    this.clearReconnect()
    this.stopPing()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.setStatus('disconnected')
  }

  subscribe(type: WsEventType, handler: EventHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)
    return () => this.handlers.get(type)?.delete(handler)
  }

  private startPing() {
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
        this.pongTimer = setTimeout(() => {
          this.ws?.close()
        }, PONG_TIMEOUT_MS)
      }
    }, PING_INTERVAL_MS)
  }

  private stopPing() {
    if (this.pingTimer) clearInterval(this.pingTimer)
    this.pingTimer = null
    this.resetPongTimeout()
  }

  private resetPongTimeout() {
    if (this.pongTimer) clearTimeout(this.pongTimer)
    this.pongTimer = null
  }

  private scheduleReconnect() {
    // H-3: Add jitter to prevent thundering herd on server deploy
    const baseDelay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, this.reconnectAttempts),
      RECONNECT_MAX_MS,
    )
    const jitter = Math.random() * baseDelay * 0.3
    const delay = baseDelay + jitter
    this.reconnectAttempts++
    this.reconnectTimer = setTimeout(() => this.connect(), delay)
  }

  private clearReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
    this.reconnectAttempts = 0
  }

  getLastSequence() {
    return this.lastSequence
  }
}

export const wsManager = new WebSocketManager()
export type { WsEventType, WsMessage, EventHandler }
