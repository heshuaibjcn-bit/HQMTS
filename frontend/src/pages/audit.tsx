import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { formatTime } from '@/lib/utils'

interface AuditEvent {
  audit_id: string
  event_type: string
  entity_type: string
  entity_id: string
  correlation_id: string
  actor: string
  description: string
  alert_level: string | null
  created_at: string
}

function AlertLevelBadge({ level }: { level: string | null }) {
  if (!level) return null
  const colors: Record<string, string> = {
    P0: 'bg-red-100 text-red-700',
    P1: 'bg-orange-100 text-orange-700',
    P2: 'bg-yellow-100 text-yellow-700',
    P3: 'bg-gray-100 text-gray-600',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${colors[level] ?? 'bg-gray-100 text-gray-600'}`}>
      {level}
    </span>
  )
}

export function AuditPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['audit', 'events'],
    queryFn: () => apiClient.get<{ events: AuditEvent[]; total: number }>('/audit/events'),
  })

  const events = data?.events ?? []

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">审计日志</h1>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        {isLoading ? (
          <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载中...</div>
        ) : events.length === 0 ? (
          <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">暂无审计记录</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">时间</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">类型</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">实体</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">操作者</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">描述</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">级别</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.audit_id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]">
                    <td className="whitespace-nowrap px-3 py-2 text-[var(--color-text-muted)]">
                      {formatTime(event.created_at)}
                    </td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-[var(--color-bg-tertiary)] px-1.5 py-0.5 font-mono text-xs">
                        {event.event_type}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-[var(--color-text-muted)]">{event.entity_type}</span>
                      <span className="ml-1 font-mono text-xs">{event.entity_id?.slice(0, 8)}</span>
                    </td>
                    <td className="px-3 py-2">{event.actor}</td>
                    <td className="max-w-xs truncate px-3 py-2">{event.description}</td>
                    <td className="px-3 py-2">
                      <AlertLevelBadge level={event.alert_level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
