import { PositionsTable } from '@/components/positions/positions-table'

export function PositionsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">持仓</h1>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <PositionsTable />
      </div>
    </div>
  )
}
