import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useAlerts } from '@/hooks/use-alerts'
import { formatTime } from '@/lib/utils'

interface HealthStatus {
  qmt: { connected: boolean; latency_ms: number }
  data_source: { connected: boolean; latency_ms: number }
  bar_aggregation: { status: string; last_bar_time: string | null }
  agent: { status: string; active_tasks: number }
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${
        ok ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'
      }`}
    />
  )
}

export function MonitoringPage() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['monitoring', 'health'],
    queryFn: () => apiClient.get<HealthStatus>('/health'),
    refetchInterval: 10_000,
  })

  const { data: alerts, isLoading: alertsLoading } = useAlerts()

  const p0p1 = (alerts ?? []).filter((a: { level: string }) => a.level === 'P0' || a.level === 'P1')

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">系统监控</h1>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* System Health */}
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">系统状态</h2>
          {healthLoading ? (
            <p className="text-sm text-[var(--color-text-muted)]">加载中...</p>
          ) : health?.qmt ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <StatusDot ok={health.qmt?.connected ?? false} />
                  <span className="text-[var(--color-text-secondary)]">QMT 连接</span>
                </div>
                <span className="text-[var(--color-text-muted)]">{health.qmt?.latency_ms ?? '--'}ms</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <StatusDot ok={health.data_source?.connected ?? false} />
                  <span className="text-[var(--color-text-secondary)]">数据源</span>
                </div>
                <span className="text-[var(--color-text-muted)]">{health.data_source?.latency_ms ?? '--'}ms</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <StatusDot ok={health.bar_aggregation?.status === 'normal'} />
                  <span className="text-[var(--color-text-secondary)]">Bar 聚合</span>
                </div>
                <span className="text-xs text-[var(--color-text-muted)]">
                  {health.bar_aggregation?.last_bar_time
                    ? formatTime(health.bar_aggregation.last_bar_time)
                    : '--'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <StatusDot ok={health.agent?.status === 'running'} />
                  <span className="text-[var(--color-text-secondary)]">Agent</span>
                </div>
                <span className="text-[var(--color-text-muted)]">
                  {health.agent?.active_tasks ?? 0} 任务
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">后端未连接</p>
          )}
        </div>

        {/* Alert Summary */}
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-[var(--color-text)]">告警</h2>
            {p0p1.length > 0 && (
              <span className="rounded-full bg-[var(--color-danger)] px-2 py-0.5 text-xs text-white">
                {p0p1.length} 紧急
              </span>
            )}
          </div>
          <div className="mt-3 space-y-2">
            {alertsLoading ? (
              <p className="text-sm text-[var(--color-text-muted)]">加载中...</p>
            ) : (alerts ?? []).length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)]">暂无告警</p>
            ) : (
              (alerts ?? []).slice(0, 8).map((alert) => (
                <div key={alert.alert_id} className="flex items-start justify-between text-sm">
                  <div className="flex items-start gap-2">
                    <span
                      className={`mt-0.5 rounded px-1 py-0.5 text-xs font-medium ${
                        alert.level === 'P0'
                          ? 'bg-red-100 text-red-700'
                          : alert.level === 'P1'
                            ? 'bg-orange-100 text-orange-700'
                            : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {alert.level}
                    </span>
                    <span className="text-[var(--color-text)]">{alert.message}</span>
                  </div>
                  <span className="shrink-0 text-xs text-[var(--color-text-muted)]">
                    {formatTime(alert.detected_at)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
