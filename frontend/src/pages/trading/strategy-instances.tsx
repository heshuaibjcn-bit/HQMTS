import { StrategyInstancesTable } from '@/components/strategies/strategy-instances-table'

export function StrategyInstancesPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">策略实例</h1>
      <p className="text-sm text-[var(--color-text-muted)]">正在运行的策略实例，按 Paper / Live 环境分组</p>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">运行实例</h2>
        <StrategyInstancesTable />
      </div>
    </div>
  )
}
