import { GitCompare } from 'lucide-react'

export function OptimizationPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">优化迭代</h1>
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-bg)] py-20">
        <GitCompare className="h-12 w-12 text-[var(--color-text-muted)]" />
        <p className="mt-4 text-lg font-medium text-[var(--color-text-secondary)]">策略优化与迭代</p>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">回测结果对比、参数敏感性分析、策略版本迭代管理</p>
        <p className="mt-4 rounded-full bg-[var(--color-bg-tertiary)] px-3 py-1 text-xs text-[var(--color-text-muted)]">即将推出</p>
      </div>
    </div>
  )
}
