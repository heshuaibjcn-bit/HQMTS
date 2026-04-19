import { StrategiesTable } from '@/components/strategies/strategies-table'
import { StrategyInstancesTable } from '@/components/strategies/strategy-instances-table'

export function StrategiesPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">策略</h1>
      <div className="space-y-4">
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">策略列表</h2>
          <StrategiesTable />
        </div>
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">运行实例</h2>
          <StrategyInstancesTable />
        </div>
      </div>
    </div>
  )
}
