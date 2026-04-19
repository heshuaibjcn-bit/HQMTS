import { useAccountSummary } from '@/hooks/use-account'
import { formatCurrency, formatPercent } from '@/lib/utils'

export function PnLCard() {
  const { data, isLoading } = useAccountSummary()

  if (isLoading) {
    return (
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <p className="text-sm text-[var(--color-text-muted)]">日内盈亏</p>
        <p className="mt-1 text-2xl font-semibold">--</p>
      </div>
    )
  }

  const pnl = data?.pnl_intraday ?? 0
  const pnlPct = data?.drawdown_intraday ?? 0
  const isPositive = pnl >= 0

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <p className="text-sm text-[var(--color-text-secondary)]">日内盈亏</p>
      <div className="mt-1 flex items-baseline gap-3">
        <p
          className={`text-2xl font-semibold ${
            isPositive ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'
          }`}
        >
          {data ? formatCurrency(pnl) : '--'}
        </p>
        {data && (
          <span
            className={`text-sm ${
              isPositive ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'
            }`}
          >
            {formatPercent(pnlPct)}
          </span>
        )}
      </div>
    </div>
  )
}
