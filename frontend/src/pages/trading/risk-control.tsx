import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useAlerts } from '@/hooks/use-alerts'
import { formatTime } from '@/lib/utils'
import { RiskLayersCard } from '@/components/risk/risk-layers-card'
import { KillSwitchPanel } from '@/components/risk/kill-switch-panel'
import { ForceFlattenPanel } from '@/components/risk/force-flatten-panel'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface HealthStatus {
  qmt: { connected: boolean; latency_ms: number }
  data_source: { connected: boolean; latency_ms: number }
  bar_aggregation: { status: string; last_bar_time: string | null }
  agent: { status: string; active_tasks: number }
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${
        ok ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'
      }`}
    />
  )
}

export function RiskControlPage() {
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.get<HealthStatus>('/health'),
    refetchInterval: 10_000,
    retry: 2,
  })
  const { data: health, isError: healthError, isLoading: healthLoading, refetch: refetchHealth } = healthQuery

  const alertsQuery = useAlerts()
  const alerts = alertsQuery.data
  const alertsError = alertsQuery.isError
  const p0p1 = (alerts ?? []).filter((a: { level: string }) => a.level === 'P0' || a.level === 'P1')

  const healthRows = health ? [
    { label: 'QMT', ok: health.qmt?.connected ?? false, value: health.qmt ? `${health.qmt.latency_ms}ms` : '--' },
    { label: '数据源', ok: health.data_source?.connected ?? false, value: health.data_source ? `${health.data_source.latency_ms}ms` : '--' },
    { label: 'Bar 聚合', ok: health.bar_aggregation?.status === 'normal', value: health.bar_aggregation?.last_bar_time ? formatTime(health.bar_aggregation.last_bar_time) : '正常' },
    { label: 'Agent', ok: health.agent?.status === 'running', value: health.agent ? `${health.agent.active_tasks} 任务` : '--' },
  ] : []

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">风控中心</h1>

      {/* System health + Alerts */}
      <ErrorBoundary>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">系统状态</h2>
          {healthError ? (
            <div className="flex flex-col items-center gap-2 py-4 text-sm">
              <AlertTriangle className="h-5 w-5 text-[var(--color-danger)]" />
              <span className="text-[var(--color-danger)]">无法获取系统状态</span>
              <button
                onClick={() => refetchHealth()}
                className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline"
              >
                <RefreshCw className="h-3 w-3" />
                重试
              </button>
            </div>
          ) : healthLoading ? (
            <div className="space-y-2">
              {['QMT', '数据源', 'Bar 聚合', 'Agent'].map((label) => (
                <div key={label} className="flex items-center justify-between text-sm">
                  <span className="text-[var(--color-text-secondary)]">{label}</span>
                  <span className="text-[var(--color-text-muted)]">--</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {healthRows.map((r) => (
                <div key={r.label} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <StatusDot ok={r.ok} />
                    <span className="text-[var(--color-text-secondary)]">{r.label}</span>
                  </div>
                  <span className="text-[var(--color-text-muted)]">{r.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-[var(--color-text)]">告警</h2>
            {p0p1.length > 0 && (
              <span className="rounded-full bg-[var(--color-danger)] px-2 py-0.5 text-xs text-white">
                {p0p1.length} 紧急
              </span>
            )}
          </div>
          <div className="mt-3 space-y-2 max-h-40 overflow-auto">
            {alertsError ? (
              <div className="flex flex-col items-center gap-2 py-2 text-sm">
                <AlertTriangle className="h-4 w-4 text-[var(--color-danger)]" />
                <span className="text-[var(--color-danger)]">无法获取告警</span>
              </div>
            ) : (alerts ?? []).length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)]">暂无告警</p>
            ) : (
              (alerts ?? []).slice(0, 6).map((alert) => (
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
      </ErrorBoundary>

      {/* Risk layers + Kill Switch */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RiskLayersCard />
        <KillSwitchPanel />
      </div>

      <ForceFlattenPanel />
    </div>
  )
}
