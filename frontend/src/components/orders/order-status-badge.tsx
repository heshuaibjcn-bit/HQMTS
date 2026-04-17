export function OrderStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    submitted: 'bg-blue-100 text-blue-700',
    partial: 'bg-blue-100 text-blue-700',
    filled: 'bg-green-100 text-green-700',
    cancelled: 'bg-gray-100 text-gray-600',
    rejected: 'bg-red-100 text-red-700',
  }
  const labels: Record<string, string> = {
    pending: '待提交',
    submitted: '已提交',
    partial: '部分成交',
    filled: '已成交',
    cancelled: '已撤单',
    rejected: '已拒绝',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${styles[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {labels[status] ?? status}
    </span>
  )
}
