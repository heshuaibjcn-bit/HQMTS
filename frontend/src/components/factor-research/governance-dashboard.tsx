import { useGovernanceStats, useGovernanceTrials, type TrialRecord } from '@/hooks/use-factor-research'
import { AlertTriangle } from 'lucide-react'

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
      <div className="text-xs text-[var(--color-text-muted)]">{label}</div>
      <div className="mt-1 text-lg font-semibold text-[var(--color-text)]">{value}</div>
      {sub && <div className="text-xs text-[var(--color-text-muted)]">{sub}</div>}
    </div>
  )
}

function BudgetBar({ remaining, total }: { remaining: number; total: number }) {
  const used = total - remaining
  const pct = total > 0 ? (used / total) * 100 : 0
  const color = pct > 80 ? 'bg-red-500' : pct > 50 ? 'bg-orange-400' : 'bg-green-500'

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="text-[var(--color-text-muted)]">试验预算</span>
        <span className="text-[var(--color-text)]">
          {used} / {total}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[var(--color-bg-tertiary)]">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <div className="mt-1 text-xs text-[var(--color-text-muted)]">
        剩余 {remaining} 次试验
      </div>
    </div>
  )
}

function SignificanceBadge({ significant }: { significant: boolean }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${
      significant
        ? 'bg-green-100 text-green-700'
        : 'bg-gray-100 text-gray-500'
    }`}>
      {significant ? '显著' : '不显著'}
    </span>
  )
}

export function GovernanceDashboard() {
  const { data: stats, isLoading: statsLoading, isError: statsError } = useGovernanceStats()
  const { data: trials, isLoading: trialsLoading } = useGovernanceTrials()

  if (statsLoading) {
    return <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载治理数据...</div>
  }

  if (statsError || !stats) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-sm">
        <AlertTriangle className="h-5 w-5 text-[var(--color-danger)]" />
        <span className="text-[var(--color-danger)]">无法获取治理统计</span>
      </div>
    )
  }

  const budgetLow = stats.budget_remaining < stats.budget_total * 0.2

  return (
    <div className="space-y-4">
      {/* Warning banner */}
      {budgetLow && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          试验预算不足 20%，请控制研究试验数量以维持统计有效性
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="总试验数" value={stats.total_trials} />
        <StatCard label="显著数" value={stats.significant_count} sub={`FWER: ${(stats.family_wise_error_rate * 100).toFixed(1)}%`} />
        <StatCard label="拒绝数" value={stats.rejected_count} sub={`FDR: ${(stats.false_discovery_rate * 100).toFixed(1)}%`} />
        <StatCard label="调整后阈值" value={stats.adjusted_threshold.toFixed(4)} sub="Bonferroni 校正" />
      </div>

      {/* Budget bar */}
      <BudgetBar remaining={stats.budget_remaining} total={stats.budget_total} />

      {/* Trials table */}
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="border-b border-[var(--color-border)] px-4 py-2">
          <h3 className="text-sm font-medium text-[var(--color-text)]">试验记录</h3>
        </div>
        {trialsLoading ? (
          <div className="py-6 text-center text-xs text-[var(--color-text-muted)]">加载...</div>
        ) : (trials ?? []).length === 0 ? (
          <div className="py-6 text-center text-xs text-[var(--color-text-muted)]">暂无试验记录</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--color-border)] bg-[var(--color-bg-tertiary)]">
                  <th className="px-3 py-1.5 text-left font-medium text-[var(--color-text-secondary)]">#</th>
                  <th className="px-3 py-1.5 text-left font-medium text-[var(--color-text-secondary)]">因子</th>
                  <th className="px-3 py-1.5 text-left font-medium text-[var(--color-text-secondary)]">策略</th>
                  <th className="px-3 py-1.5 text-left font-medium text-[var(--color-text-secondary)]">指标</th>
                  <th className="px-3 py-1.5 text-right font-medium text-[var(--color-text-secondary)]">值</th>
                  <th className="px-3 py-1.5 text-right font-medium text-[var(--color-text-secondary)]">阈值</th>
                  <th className="px-3 py-1.5 text-center font-medium text-[var(--color-text-secondary)]">显著</th>
                </tr>
              </thead>
              <tbody>
                {(trials ?? []).map((t: TrialRecord) => (
                  <tr key={t.trial_id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]">
                    <td className="px-3 py-1.5 text-[var(--color-text-muted)]">{t.trial_id}</td>
                    <td className="px-3 py-1.5 font-mono text-[var(--color-text)]">{t.factor_name}</td>
                    <td className="px-3 py-1.5 text-[var(--color-text-secondary)]">{t.strategy_name}</td>
                    <td className="px-3 py-1.5 text-[var(--color-text-secondary)]">{t.metric_name}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-[var(--color-text)]">{t.metric_value.toFixed(4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-[var(--color-text-muted)]">{t.threshold.toFixed(4)}</td>
                    <td className="px-3 py-1.5 text-center"><SignificanceBadge significant={t.is_significant} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
