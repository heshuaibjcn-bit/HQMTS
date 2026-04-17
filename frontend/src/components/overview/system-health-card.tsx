import { Activity } from 'lucide-react'

export function SystemHealthCard() {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-[var(--color-text-muted)]" />
        <p className="text-sm text-[var(--color-text-secondary)]">系统状态</p>
      </div>
      <div className="mt-2 space-y-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--color-text-secondary)]">QMT</span>
          <span className="text-[var(--color-text-muted)]">--</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--color-text-secondary)]">数据源</span>
          <span className="text-[var(--color-text-muted)]">--</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--color-text-secondary)]">Agent</span>
          <span className="text-[var(--color-text-muted)]">--</span>
        </div>
      </div>
    </div>
  )
}
