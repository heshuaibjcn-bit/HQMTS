import { ScrollText } from 'lucide-react'

export function AuditReportsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">审计报告</h1>
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-bg)] py-20">
        <ScrollText className="h-12 w-12 text-[var(--color-text-muted)]" />
        <p className="mt-4 text-lg font-medium text-[var(--color-text-secondary)]">结构化审计报告</p>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">交易合规报告、策略绩效评估、风险事件复盘</p>
        <p className="mt-4 rounded-full bg-[var(--color-bg-tertiary)] px-3 py-1 text-xs text-[var(--color-text-muted)]">即将推出</p>
      </div>
    </div>
  )
}
