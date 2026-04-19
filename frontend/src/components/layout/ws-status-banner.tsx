import { useWsStore } from '@/stores/ws-store'
import { WifiOff } from 'lucide-react'

export function WsStatusBanner() {
  const isDisconnected = useWsStore((s) => s.status === 'disconnected')

  if (!isDisconnected) return null

  return (
    <div className="flex items-center gap-2 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      <WifiOff className="h-4 w-4" />
      <span>实时连接已断开，数据可能已过时。正在尝试重新连接...</span>
    </div>
  )
}
