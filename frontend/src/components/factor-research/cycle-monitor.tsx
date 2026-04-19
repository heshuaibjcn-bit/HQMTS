import { useState } from 'react'
import {
  useResearchCycles,
  useCreateCycle,
  useCancelCycle,
  type ResearchCycle,
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

const OPPORTUNITY_LABELS: Record<string, string> = {
  human_initiated: '人工发起',
  market_anomaly: '市场异常',
  regime_change: '制度变化',
  factor_decay: '因子衰减',
  strategy_degradation: '策略退化',
}

const STATUS_COLORS: Record<string, string> = {
  opportunity_identified: '#6b7280',
  researching: '#3b82f6',
  factor_validated: '#8b5cf6',
  synthesizing: '#f59e0b',
  backtesting: '#06b6d4',
  evaluating: '#f97316',
  promoted: '#10b981',
  archived: '#9ca3af',
  re_research: '#ef4444',
  canceled: '#6b7280',
  failed: '#ef4444',
}

const CYCLE_STAGES = [
  'opportunity_identified',
  'researching',
  'factor_validated',
  'synthesizing',
  'backtesting',
  'evaluating',
]

function stageIndex(status: string): number {
  const idx = CYCLE_STAGES.indexOf(status)
  return idx >= 0 ? idx : -1
}

interface CycleMonitorProps {
  onSelectCycle?: (cycleId: string) => void
}

export function CycleMonitor({ onSelectCycle }: CycleMonitorProps) {
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const { data, isLoading } = useResearchCycles(statusFilter)
  const createCycle = useCreateCycle()
  const cancelCycle = useCancelCycle()
  const [showCreate, setShowCreate] = useState(false)

  if (isLoading) {
    return <div className="py-8 text-center text-sm text-[var(--color-text-secondary)]">加载中...</div>
  }

  const cycles = data?.cycles ?? []

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-[var(--color-text-secondary)]">
            共 {data?.total ?? 0} 个研发循环
          </span>
          <select
            value={statusFilter ?? ''}
            onChange={(e) => setStatusFilter(e.target.value || undefined)}
            className="rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]"
          >
            <option value="">全部状态</option>
            <option value="opportunity_identified">机会识别</option>
            <option value="researching">因子研究</option>
            <option value="factor_validated">因子验证</option>
            <option value="synthesizing">策略合成</option>
            <option value="backtesting">回测中</option>
            <option value="evaluating">评估中</option>
            <option value="promoted">已推广</option>
            <option value="archived">已归档</option>
          </select>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
        >
          新建循环
        </button>
      </div>

      {showCreate && (
        <CreateCycleForm
          onSubmit={async (vals) => {
            await createCycle.mutateAsync(vals)
            setShowCreate(false)
          }}
          onCancel={() => setShowCreate(false)}
          isLoading={createCycle.isPending}
        />
      )}

      {cycles.length === 0 ? (
        <div className="py-12 text-center text-sm text-[var(--color-text-secondary)]">
          暂无研发循环。点击「新建循环」启动自主因子研发。
        </div>
      ) : (
        <div className="grid gap-3">
          {cycles.map((cycle) => (
            <CycleCard
              key={cycle.research_cycle_id}
              cycle={cycle}
              onSelect={() => onSelectCycle?.(cycle.research_cycle_id)}
              onCancel={
                !['promoted', 'archived', 'canceled', 'failed'].includes(cycle.status)
                  ? () => cancelCycle.mutate(cycle.research_cycle_id)
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </div>
  )
}

function CycleCard({
  cycle,
  onSelect,
  onCancel,
}: {
  cycle: ResearchCycle
  onSelect: () => void
  onCancel?: () => void
}) {
  const sIdx = stageIndex(cycle.status)
  const isTerminal = ['promoted', 'archived', 'canceled', 'failed'].includes(cycle.status)
  const discoveries = cycle.factor_discovery_ids?.length ?? 0
  const candidates = cycle.strategy_candidate_ids?.length ?? 0

  return (
    <div
      onClick={onSelect}
      className="cursor-pointer rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4 transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-medium text-[var(--color-text)]">
            {cycle.title}
          </h3>
          <p className="mt-0.5 text-[10px] text-[var(--color-text-secondary)]">
            {OPPORTUNITY_LABELS[cycle.opportunity_type] ?? cycle.opportunity_type}
            {' · '}
            由 {cycle.triggered_by || '系统'} 触发
          </p>
        </div>
        <span
          className="ml-2 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
          style={{ backgroundColor: STATUS_COLORS[cycle.status] ?? '#6b7280' }}
        >
          {STATUS_LABELS[cycle.status] ?? cycle.status}
        </span>
      </div>

      {/* Progress bar */}
      {!isTerminal && sIdx >= 0 && (
        <div className="mt-3 flex items-center gap-1">
          {CYCLE_STAGES.map((stage, i) => (
            <div
              key={stage}
              className="h-1.5 flex-1 rounded-full transition-colors"
              style={{
                backgroundColor:
                  i <= sIdx ? STATUS_COLORS[cycle.status] : 'var(--color-bg-tertiary)',
              }}
            />
          ))}
        </div>
      )}

      <div className="mt-2 flex items-center gap-3 text-[10px] text-[var(--color-text-secondary)]">
        <span>因子发现: {discoveries}</span>
        <span>策略候选: {candidates}</span>
        <span>自治: {cycle.autonomy_level.replace('level_', 'L')}</span>
        {cycle.budget_consumed && (
          <span>
            预算: {cycle.budget_consumed.trials}/{cycle.budget.max_trials} 试验
          </span>
        )}
        {onCancel && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onCancel()
            }}
            className="ml-auto text-[10px] text-red-400 hover:text-red-300"
          >
            取消
          </button>
        )}
      </div>
    </div>
  )
}

function CreateCycleForm({
  onSubmit,
  onCancel,
  isLoading,
}: {
  onSubmit: (vals: {
    title: string
    research_question?: string
    opportunity_type?: string
    autonomy_level?: string
  }) => void
  onCancel: () => void
  isLoading: boolean
}) {
  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const [autonomy, setAutonomy] = useState('level_2')

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4 space-y-3">
      <h3 className="text-sm font-medium text-[var(--color-text)]">创建研发循环</h3>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="循环标题"
        className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-1.5 text-xs text-[var(--color-text)]"
      />
      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="研究问题（可选，留空则不创建关联项目）"
        className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-1.5 text-xs text-[var(--color-text)]"
      />
      <select
        value={autonomy}
        onChange={(e) => setAutonomy(e.target.value)}
        className="rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-1.5 text-xs text-[var(--color-text)]"
      >
        <option value="level_1">L1: AI建议，人工决定</option>
        <option value="level_2">L2: AI决策，关键节点审批（默认）</option>
        <option value="level_3">L3: AI自主，人工通知</option>
      </select>
      <div className="flex gap-2">
        <button
          onClick={() => onSubmit({ title, research_question: question || undefined, autonomy_level: autonomy })}
          disabled={!title || isLoading}
          className="rounded bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {isLoading ? '创建中...' : '创建'}
        </button>
        <button
          onClick={onCancel}
          className="rounded border border-[var(--color-border)] px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
        >
          取消
        </button>
      </div>
    </div>
  )
}
