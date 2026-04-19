import type { Position } from '@/hooks/use-positions'
import { formatCurrency } from '@/lib/utils'
import { X } from 'lucide-react'

interface Props {
  position: Position
  onClose: () => void
}

export function PositionDetailDialog({ position, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-lg bg-[var(--color-bg)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            {position.instrument_code} {position.instrument_name}
          </h2>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <Detail label="方向" value={position.direction === 'long' ? '多' : '空'} />
          <Detail label="数量" value={String(position.quantity)} />
          <Detail label="可卖数量" value={String(position.available_quantity)} />
          <Detail label="成本价" value={formatCurrency(position.avg_cost)} />
          <Detail label="市值" value={formatCurrency(position.market_value)} />
          <Detail label="浮盈" value={formatCurrency(position.unrealized_pnl)} />
          <Detail label="浮盈比" value={`${(position.unrealized_pnl_pct * 100).toFixed(2)}%`} />
        </div>
      </div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <p className="font-medium text-[var(--color-text)]">{value}</p>
    </div>
  )
}
