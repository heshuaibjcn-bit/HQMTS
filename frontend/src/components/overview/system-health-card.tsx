import { Activity } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface HealthStatus {
  qmt: { connected: boolean; latency_ms: number }
  data_source: { connected: boolean; latency_ms: number }
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

export function SystemHealthCard() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.get<HealthStatus>('/health'),
    refetchInterval: 30_000,
  })

  const rows = [
    { label: 'QMT', ok: health?.qmt?.connected ?? false, value: health?.qmt ? `${health.qmt.latency_ms}ms` : '--' },
    { label: '数据源', ok: health?.data_source?.connected ?? false, value: health?.data_source ? `${health.data_source.latency_ms}ms` : '--' },
    { label: 'Agent', ok: health?.agent?.status === 'running', value: health?.agent ? `${health.agent.active_tasks} 任务` : '--' },
  ]

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-[var(--color-text-muted)]" />
        <p className="text-sm text-[var(--color-text-secondary)]">系统状态</p>
      </div>
      <div className="mt-2 space-y-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <StatusDot ok={r.ok} />
              <span className="text-[var(--color-text-secondary)]">{r.label}</span>
            </div>
            <span className="text-[var(--color-text-muted)]">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
