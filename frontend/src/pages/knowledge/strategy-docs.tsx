import { FileCode2 } from 'lucide-react'

export function StrategyDocsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">策略文档</h1>
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-bg)] py-20">
        <FileCode2 className="h-12 w-12 text-[var(--color-text-muted)]" />
        <p className="mt-4 text-lg font-medium text-[var(--color-text-secondary)]">策略文档管理</p>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">策略设计文档、研究报告、交易日志、知识沉淀</p>
        <p className="mt-4 rounded-full bg-[var(--color-bg-tertiary)] px-3 py-1 text-xs text-[var(--color-text-muted)]">即将推出</p>
      </div>
    </div>
  )
}
