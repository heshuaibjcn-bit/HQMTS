import { useEffect, useRef } from 'react'
import { wsManager, type WsEventType, type EventHandler } from '@/lib/websocket'
import { useWsStore } from '@/stores/ws-store'

export function useWSSubscription(type: WsEventType, handler: EventHandler) {
  // H-6: Stabilize handler with useRef to prevent re-subscribe on every render
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    const stableHandler: EventHandler = (msg) => handlerRef.current(msg)
    const unsub = wsManager.subscribe(type, stableHandler)
    return () => { unsub() }
  }, [type])
}

export function useWSStatus() {
  const status = useWsStore((s) => s.status)
  const setStatus = useWsStore((s) => s.setStatus)

  useEffect(() => {
    const unsub = wsManager.onStatusChange((s) => setStatus(s as typeof status))
    return () => { unsub() }
  }, [setStatus])

  useEffect(() => {
    wsManager.connect()
    return () => { wsManager.disconnect() }
  }, [])

  return status
}
