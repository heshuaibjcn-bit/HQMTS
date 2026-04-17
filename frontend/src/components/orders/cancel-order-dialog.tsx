import { useState } from 'react'
import type { Order } from '@/hooks/use-orders'
import { useCancelOrder } from '@/hooks/use-orders'
import { X } from 'lucide-react'

interface Props {
  order: Order
  onClose: () => void
}

export function CancelOrderDialog({ order, onClose }: Props) {
  const cancelOrder = useCancelOrder()
  const [loading, setLoading] = useState(false)

  const handleCancel = async () => {
    setLoading(true)
    try {
      await cancelOrder.mutateAsync(order.order_id)
      onClose()
    } catch {
      // error handled by mutation
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-lg bg-[var(--color-bg)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">确认撤单</h2>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
          确认撤销订单 {order.instrument_code} {order.direction === 'buy' ? '买入' : '卖出'}{' '}
          {order.quantity}股 @ {order.price}？
        </p>
        {cancelOrder.isError && (
          <p className="mt-2 text-sm text-[var(--color-danger)]">撤单失败，请重试</p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]"
          >
            取消
          </button>
          <button
            onClick={handleCancel}
            disabled={loading}
            className="rounded-md bg-[var(--color-danger)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
          >
            {loading ? '撤单中...' : '确认撤单'}
          </button>
        </div>
      </div>
    </div>
  )
}
