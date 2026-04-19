import { useNotificationStore } from '@/stores/notification-store'
import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react'

export function ToastContainer() {
  const notifications = useNotificationStore((s) => s.notifications)
  const remove = useNotificationStore((s) => s.removeNotification)

  if (notifications.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {notifications.map((n) => (
        <div
          key={n.id}
          className={`flex items-start gap-2 rounded-lg border px-4 py-3 shadow-lg transition-all ${
            n.type === 'error'
              ? 'border-red-200 bg-red-50 text-red-800'
              : n.type === 'warning'
                ? 'border-amber-200 bg-amber-50 text-amber-800'
                : n.type === 'success'
                  ? 'border-green-200 bg-green-50 text-green-800'
                  : 'border-blue-200 bg-blue-50 text-blue-800'
          }`}
        >
          <div className="mt-0.5">
            {n.type === 'error' && <AlertCircle className="h-4 w-4" />}
            {n.type === 'warning' && <AlertTriangle className="h-4 w-4" />}
            {n.type === 'success' && <CheckCircle className="h-4 w-4" />}
            {n.type === 'info' && <Info className="h-4 w-4" />}
          </div>
          <p className="flex-1 text-sm">{n.message}</p>
          <button
            onClick={() => remove(n.id)}
            className="shrink-0 text-current opacity-50 hover:opacity-100"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}
