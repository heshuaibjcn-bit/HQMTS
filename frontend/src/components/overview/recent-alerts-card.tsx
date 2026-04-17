import { useAlerts } from '@/hooks/use-alerts'
import { formatTime } from '@/lib/utils'
import { AlertTriangle } from 'lucide-react'

export function RecentAlertsCard() {
  const { data, isLoading } = useAlerts()

  const urgentAlerts = data?.filter((a) => a.level === 'P0' || a.level === 'P1') ?? []

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-[var(--color-warning)]" />
          <p className="text-sm font-medium text-[var(--color-text)]">最新告警</p>
        </div>
        {urgentAlerts.length > 0 && (
          <span className="rounded-full bg-[var(--color-danger)] px-2 py-0.5 text-xs text-white">
            {urgentAlerts.length}
          </span>
        )}
      </div>
      <div className="mt-3 space-y-2">
        {isLoading ? (
          <p className="text-sm text-[var(--color-text-muted)]">加载中...</p>
        ) : data && data.length > 0 ? (
          data.slice(0, 5).map((alert) => (
            <div key={alert.alert_id} className="flex items-start justify-between">
              <div className="flex items-start gap-2">
                <span
                  className={`mt-0.5 rounded px-1 py-0.5 text-xs font-medium ${
                    alert.level === 'P0'
                      ? 'bg-red-100 text-red-700'
                      : alert.level === 'P1'
                        ? 'bg-orange-100 text-orange-700'
                        : alert.level === 'P2'
                          ? 'bg-yellow-100 text-yellow-700'
                          : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {alert.level}
                </span>
                <p className="text-sm text-[var(--color-text)]">{alert.message}</p>
              </div>
              <span className="shrink-0 text-xs text-[var(--color-text-muted)]">
                {formatTime(alert.detected_at)}
              </span>
            </div>
          ))
        ) : (
          <p className="text-sm text-[var(--color-text-muted)]">暂无告警</p>
        )}
      </div>
    </div>
  )
}
