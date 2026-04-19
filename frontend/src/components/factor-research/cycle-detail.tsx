import {
  useResearchCycle,
  useCycleDiscoveries,
  useCycleCandidates,
  useApproveCandidatePaper,
  useRejectCandidate,
  useCancelCycle,
} from '@/hooks/use-factor-research'

const STATUS_LABELS: Record<string, string> = {
  opportunity_identified: '机会识别',
  researching: '因子研究',
  factor_validated: '因子验证',
  synthesizing: '策略合成',
  backtesting: '回测中',
  evaluating: '评估中',
  promoted: '已推广',
  archived: '已归档',
  re_research: '重新研究',
  canceled: '已取消',
  failed: '失败',
}

const DISCOVERY_STATUS_LABELS: Record<string, string> = {
  candidate: '候选',
  validated: '已验证',
  registered: '已注册',
  expired: '已过期',
}

interface CycleDetailProps {
  cycleId: string
  onBack: () => void
}

export function CycleDetail({ cycleId, onBack }: CycleDetailProps) {
  const { data: cycle, isLoading } = useResearchCycle(cycleId)
  const { data: discoveriesData } = useCycleDiscoveries(cycleId)
  const { data: candidatesData } = useCycleCandidates(cycleId)
  const approvePaper = useApproveCandidatePaper()
  const rejectCandidate = useRejectCandidate()
  const cancelCycle = useCancelCycle()

  if (isLoading || !cycle) {
    return <div className="py-8 text-center text-sm text-[var(--color-text-secondary)]">加载中...</div>
  }

  const isTerminal = ['promoted', 'archived', 'canceled', 'failed'].includes(cycle.status)
  const discoveries = discoveriesData?.discoveries ?? []
  const candidates = candidatesData?.candidates ?? []

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
        >
          &larr; 返回列表
        </button>
        <h2 className="text-sm font-medium text-[var(--color-text)]">{cycle.title}</h2>
        {!isTerminal && (
          <button
            onClick={() => cancelCycle.mutate(cycleId)}
            className="ml-auto rounded border border-red-400 px-2 py-0.5 text-[10px] text-red-400 hover:bg-red-400 hover:text-white"
          >
            取消循环
          </button>
        )}
      </div>

      {/* Status & budget */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
          <div className="text-[10px] text-[var(--color-text-secondary)]">当前状态</div>
          <div className="mt-1 text-sm font-medium text-[var(--color-text)]">
            {STATUS_LABELS[cycle.status] ?? cycle.status}
          </div>
        </div>
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
          <div className="text-[10px] text-[var(--color-text-secondary)]">预算消耗</div>
          <div className="mt-1 text-sm text-[var(--color-text)]">
            试验 {cycle.budget_consumed.trials}/{cycle.budget.max_trials}
            {' · '}
            回测 {cycle.budget_consumed.backtests}/{cycle.budget.max_backtests}
          </div>
        </div>
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
          <div className="text-[10px] text-[var(--color-text-secondary)]">自治级别</div>
          <div className="mt-1 text-sm text-[var(--color-text)]">
            {cycle.autonomy_level.replace('level_', 'L')}
            {' · '}
            由 {cycle.triggered_by || '系统'} 触发
          </div>
        </div>
      </div>

      {/* Factor Discoveries */}
      <div className="space-y-2">
        <h3 className="text-xs font-medium text-[var(--color-text)]">
          因子发现 ({discoveries.length})
        </h3>
        {discoveries.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--color-border)] py-6 text-center text-xs text-[var(--color-text-secondary)]">
            暂无因子发现
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
            <table className="w-full text-xs">
              <thead className="bg-[var(--color-bg-tertiary)]">
                <tr>
                  <th className="px-3 py-2 text-left text-[10px] font-medium text-[var(--color-text-secondary)]">因子组合</th>
                  <th className="px-3 py-2 text-left text-[10px] font-medium text-[var(--color-text-secondary)]">类型</th>
                  <th className="px-3 py-2 text-right text-[10px] font-medium text-[var(--color-text-secondary)]">指标值</th>
                  <th className="px-3 py-2 text-center text-[10px] font-medium text-[var(--color-text-secondary)]">显著</th>
                  <th className="px-3 py-2 text-right text-[10px] font-medium text-[var(--color-text-secondary)]">置信度</th>
                  <th className="px-3 py-2 text-left text-[10px] font-medium text-[var(--color-text-secondary)]">制度</th>
                  <th className="px-3 py-2 text-left text-[10px] font-medium text-[var(--color-text-secondary)]">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {discoveries.map((d) => (
                  <tr key={d.factor_discovery_id} className="hover:bg-[var(--color-bg-secondary)]">
                    <td className="px-3 py-2 text-[var(--color-text)]">
                      {d.factor_names.join(', ')}
                    </td>
                    <td className="px-3 py-2 text-[var(--color-text-secondary)]">{d.discovery_type}</td>
                    <td className="px-3 py-2 text-right text-[var(--color-text)]">{d.metric_value.toFixed(3)}</td>
                    <td className="px-3 py-2 text-center">
                      {d.is_significant ? (
                        <span className="text-green-500">Y</span>
                      ) : (
                        <span className="text-[var(--color-text-secondary)]">N</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right text-[var(--color-text)]">{(d.confidence * 100).toFixed(0)}%</td>
                    <td className="px-3 py-2 text-[var(--color-text-secondary)]">{d.market_regime || '-'}</td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-[var(--color-bg-tertiary)] px-1.5 py-0.5 text-[10px]">
                        {DISCOVERY_STATUS_LABELS[d.status] ?? d.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Strategy Candidates */}
      <div className="space-y-2">
        <h3 className="text-xs font-medium text-[var(--color-text)]">
          策略候选 ({candidates.length})
        </h3>
        {candidates.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--color-border)] py-6 text-center text-xs text-[var(--color-text-secondary)]">
            暂无策略候选
          </div>
        ) : (
          <div className="grid gap-2">
            {candidates.map((c) => (
              <div
                key={c.strategy_candidate_id}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-medium text-[var(--color-text)]">
                      {c.strategy_template_name || '未命名策略'}
                    </span>
                    <span className="ml-2 text-[10px] text-[var(--color-text-secondary)]">
                      源因子: {c.source_factors.join(', ')}
                    </span>
                  </div>
                  <span className="rounded-full bg-[var(--color-bg-tertiary)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]">
                    {c.status}
                  </span>
                </div>
                {c.backtest_sharpe != null && (
                  <div className="mt-2 flex gap-4 text-[10px] text-[var(--color-text-secondary)]">
                    <span>Sharpe: {c.backtest_sharpe.toFixed(2)}</span>
                    <span>收益: {((c.backtest_return ?? 0) * 100).toFixed(1)}%</span>
                    <span>回撤: {((c.backtest_drawdown ?? 0) * 100).toFixed(1)}%</span>
                    {c.backtest_trades != null && <span>交易: {c.backtest_trades}</span>}
                    {c.evaluation_score != null && <span>评分: {c.evaluation_score.toFixed(2)}</span>}
                  </div>
                )}
                {c.ai_rationale && (
                  <p className="mt-1 text-[10px] text-[var(--color-text-secondary)] line-clamp-2">
                    {c.ai_rationale}
                  </p>
                )}
                {c.status === 'evaluated' && (
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => approvePaper.mutate(c.strategy_candidate_id)}
                      className="rounded bg-[var(--color-primary)] px-2 py-0.5 text-[10px] font-medium text-white hover:opacity-90"
                    >
                      审批 Paper 部署
                    </button>
                    <button
                      onClick={() => rejectCandidate.mutate(c.strategy_candidate_id)}
                      className="rounded border border-red-400 px-2 py-0.5 text-[10px] text-red-400 hover:bg-red-400 hover:text-white"
                    >
                      拒绝
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
