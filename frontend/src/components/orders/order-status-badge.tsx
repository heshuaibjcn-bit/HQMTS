export function OrderStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    created: 'bg-gray-100 text-gray-600',
    pending_submit: 'bg-yellow-100 text-yellow-700',
    pending: 'bg-yellow-100 text-yellow-700',
    submitted: 'bg-blue-100 text-blue-700',
    accepted: 'bg-blue-100 text-blue-700',
    partial: 'bg-blue-100 text-blue-700',
    partial_filled: 'bg-blue-100 text-blue-700',
    filled: 'bg-green-100 text-green-700',
    cancelled: 'bg-gray-100 text-gray-600',
    canceled: 'bg-gray-100 text-gray-600',
    rejected: 'bg-red-100 text-red-700',
    error: 'bg-red-100 text-red-700',
    suspended: 'bg-orange-100 text-orange-700',
    expired: 'bg-gray-100 text-gray-600',
  }
  const labels: Record<string, string> = {
    created: '已创建',
    pending_submit: '待提交',
    pending: '待提交',
    submitted: '已提交',
    accepted: '已接受',
    partial: '部分成交',
    partial_filled: '部分成交',
    filled: '已成交',
    cancelled: '已撤单',
    canceled: '已撤单',
    rejected: '已拒绝',
    error: '异常',
    suspended: '已挂起',
    expired: '已过期',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${styles[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {labels[status] ?? status}
    </span>
  )
}
