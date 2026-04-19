import { StrategiesTable } from '@/components/strategies/strategies-table'
import { LifecycleBreadcrumb } from '@/components/shared/lifecycle-breadcrumb'

export function StrategyDevPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[var(--color-text)]">策略开发</h1>
        <LifecycleBreadcrumb currentStage="research" />
      </div>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">策略列表</h2>
        <StrategiesTable />
      </div>
    </div>
  )
}
