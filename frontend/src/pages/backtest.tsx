import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { formatTime } from '@/lib/utils'

interface BacktestTask {
  task_id: string
  strategy_name: string
  version: string
  instruments: string[]
  start_date: string
  end_date: string
  status: string
  created_at: string
}

function BacktestStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
  }
  const labels: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${styles[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {labels[status] ?? status}
    </span>
  )
}

export function BacktestPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['backtest', 'tasks'],
    queryFn: () => apiClient.get<{ tasks: BacktestTask[] }>('/backtest/tasks'),
  })

  const tasks = data?.tasks ?? []

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">回测与验证</h1>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">回测任务</h2>
        {isLoading ? (
          <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载中...</div>
        ) : tasks.length === 0 ? (
          <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">暂无回测任务</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">策略</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">版本</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">标的</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">时间范围</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">状态</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">创建时间</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.task_id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]">
                    <td className="px-3 py-2 font-medium">{task.strategy_name}</td>
                    <td className="px-3 py-2">{task.version}</td>
                    <td className="px-3 py-2">{task.instruments.join(', ')}</td>
                    <td className="px-3 py-2">
                      {task.start_date} ~ {task.end_date}
                    </td>
                    <td className="px-3 py-2">
                      <BacktestStatusBadge status={task.status} />
                    </td>
                    <td className="px-3 py-2 text-[var(--color-text-muted)]">
                      {formatTime(task.created_at)}
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
