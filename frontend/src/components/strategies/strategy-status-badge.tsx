export function StrategyStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    running: 'bg-green-100 text-green-700',
    stopped: 'bg-gray-100 text-gray-600',
    paused: 'bg-yellow-100 text-yellow-700',
    error: 'bg-red-100 text-red-700',
    initializing: 'bg-blue-100 text-blue-700',
  }
  const labels: Record<string, string> = {
    running: '运行中',
    stopped: '已停止',
    paused: '已暂停',
    error: '错误',
    initializing: '初始化',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${styles[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {labels[status] ?? status}
    </span>
  )
}
