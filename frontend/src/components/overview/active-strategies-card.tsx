import { useAccountSummary } from '@/hooks/use-account'
import { Cpu } from 'lucide-react'

export function ActiveStrategiesCard() {
  const { data, isLoading } = useAccountSummary()

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <div className="flex items-center gap-2">
        <Cpu className="h-4 w-4 text-[var(--color-text-muted)]" />
        <p className="text-sm text-[var(--color-text-secondary)]">活跃策略</p>
      </div>
      <p className="mt-1 text-2xl font-semibold">
        {isLoading ? '--' : data?.active_strategies ?? 0}
      </p>
      <p className="mt-1 text-xs text-[var(--color-text-muted)]">
        持仓 {isLoading ? '--' : data?.positions_count ?? 0} 只
      </p>
    </div>
  )
}
