import { useAccountSummary } from '@/hooks/use-account'
import { formatCurrency } from '@/lib/utils'

export function AccountSummaryCard() {
  const { data, isLoading } = useAccountSummary()

  if (isLoading) {
    return (
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <p className="text-sm text-[var(--color-text-muted)]">总资产</p>
        <p className="mt-1 text-2xl font-semibold">--</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <p className="text-sm text-[var(--color-text-secondary)]">总资产</p>
          <p className="mt-1 text-xl font-semibold">
            {data ? formatCurrency(data.total_asset) : '--'}
          </p>
        </div>
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <p className="text-sm text-[var(--color-text-secondary)]">可用资金</p>
          <p className="mt-1 text-xl font-semibold">
            {data ? formatCurrency(data.available_cash) : '--'}
          </p>
        </div>
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <p className="text-sm text-[var(--color-text-secondary)]">冻结资金</p>
          <p className="mt-1 text-xl font-semibold">
            {data ? formatCurrency(data.frozen_cash) : '--'}
          </p>
        </div>
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <p className="text-sm text-[var(--color-text-secondary)]">持仓市值</p>
          <p className="mt-1 text-xl font-semibold">
            {data ? formatCurrency(data.market_value) : '--'}
          </p>
        </div>
      </div>
    </div>
  )
}
