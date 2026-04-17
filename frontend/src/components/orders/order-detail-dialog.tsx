import type { Order } from '@/hooks/use-orders'
import { formatCurrency, formatTime } from '@/lib/utils'
import { OrderStatusBadge } from './order-status-badge'
import { X } from 'lucide-react'

interface Props {
  order: Order
  onClose: () => void
}

export function OrderDetailDialog({ order, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-lg bg-[var(--color-bg)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            订单详情 {order.order_id.slice(0, 8)}
          </h2>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <Detail label="标的" value={`${order.instrument_code} ${order.instrument_name}`} />
          <Detail label="方向" value={order.direction === 'buy' ? '买入' : '卖出'} />
          <Detail label="订单类型" value={order.order_type} />
          <Detail label="价格" value={formatCurrency(order.price)} />
          <Detail label="委托数量" value={String(order.quantity)} />
          <Detail label="成交数量" value={String(order.filled_quantity)} />
          <Detail label="状态" value={<OrderStatusBadge status={order.status} />} />
          <Detail label="创建时间" value={formatTime(order.created_at)} />
          <Detail label="更新时间" value={formatTime(order.updated_at)} />
        </div>
      </div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <p className="font-medium text-[var(--color-text)]">{value}</p>
    </div>
  )
}
