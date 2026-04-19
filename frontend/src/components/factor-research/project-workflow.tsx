import { useState, useCallback, useRef, useEffect } from 'react'
import {
  useResearchProject,
  useAdvanceProjectStage,
  useCancelProject,
  useProjectHypotheses,
  useUpdateHypothesis,
  useProjectGovernance,
  useCreateHypothesis,
  useDesignTrialPlan,
  useExecuteTrial,
  useValidateTrial,
  useRollbackProject,
  streamProjectExploration,
  type Hypothesis,
  type TrialPlan,
} from '@/hooks/use-factor-research'
import { useNotificationStore } from '@/stores/notification-store'
import { Loader2, Send, Bot, User, AlertTriangle, CheckCircle, XCircle, Play, Shield } from 'lucide-react'

const STAGES = [
  { key: 'exploration', label: '探索', status: 'exploring' },
  { key: 'hypothesis', label: '假设', status: 'hypothesizing' },
  { key: 'design', label: '设计', status: 'designing' },
  { key: 'execution', label: '执行', status: 'executing' },
  { key: 'validation', label: '验证', status: 'validating' },
  { key: 'report', label: '报告', status: 'reporting' },
] as const

const STATUS_LABELS: Record<string, string> = {
  created: '已创建',
  exploring: '探索中',
  hypothesizing: '假设阶段',
  designing: '设计阶段',
  executing: '执行中',
  validating: '验证中',
  reporting: '撰写报告',
  completed: '已完成',
  failed: '失败',
  canceled: '已取消',
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface ProjectWorkflowProps {
  projectId: string
  onBack?: () => void
}

export function ProjectWorkflow({ projectId, onBack }: ProjectWorkflowProps) {
  const { data: project, isLoading } = useResearchProject(projectId)
  const advanceStage = useAdvanceProjectStage()
  const cancelProject = useCancelProject()
  const { data: hypothesesData } = useProjectHypotheses(projectId)
  const updateHypothesis = useUpdateHypothesis()
  const createHypothesis = useCreateHypothesis()
  const designTrialPlan = useDesignTrialPlan()
  const executeTrial = useExecuteTrial()
  const validateTrial = useValidateTrial()
  const rollbackProject = useRollbackProject()
  const { data: governanceStats } = useProjectGovernance(projectId)
  const notify = useNotificationStore((s) => s.addNotification)

  // Exploration chat state
  const [exploreMessages, setExploreMessages] = useState<ChatMessage[]>([])
  const [exploreInput, setExploreInput] = useState('')
  const [exploreSending, setExploreSending] = useState(false)
  const [exploreStreaming, setExploreStreaming] = useState<string | null>(null)
  const exploreAbortRef = useRef<AbortController | null>(null)
  const exploreScrollRef = useRef<HTMLDivElement>(null)

  // Design form state
  const [designForm, setDesignForm] = useState({
    hypothesisId: '',
    factorCombination: '',
    instruments: '',
    trainStart: '',
    trainEnd: '',
    testStart: '',
    testEnd: '',
    metricName: 'sharpe_ratio',
    metricThreshold: '0.5',
  })

  const hypotheses = hypothesesData?.hypotheses ?? []
  const trialPlans = project?.trial_plans ?? []

  useEffect(() => {
    return () => { exploreAbortRef.current?.abort() }
  }, [])

  useEffect(() => {
    if (exploreScrollRef.current) {
      exploreScrollRef.current.scrollTop = exploreScrollRef.current.scrollHeight
    }
  }, [exploreMessages, exploreStreaming])

  // Auto-fill design form with first accepted hypothesis
  useEffect(() => {
    if (project?.status === 'designing' && hypotheses.length > 0 && !designForm.hypothesisId) {
      const accepted = hypotheses.find((h) => h.status === 'accepted')
      if (accepted) {
        setDesignForm((prev) => ({
          ...prev,
          hypothesisId: accepted.hypothesis_id,
          factorCombination: accepted.factor_names.join(', '),
          instruments: accepted.instrument_scope.join(', '),
        }))
      }
    }
  }, [project?.status, hypotheses, designForm.hypothesisId])

  const handleExploreSend = useCallback(async () => {
    if (!exploreInput.trim() || exploreSending) return
    const content = exploreInput.trim()
    const userMsg: ChatMessage = { id: `u_${Date.now()}`, role: 'user', content }
    setExploreMessages((prev) => [...prev, userMsg])
    setExploreInput('')
    setExploreSending(true)
    setExploreStreaming('')

    exploreAbortRef.current?.abort()
    const controller = new AbortController()
    exploreAbortRef.current = controller

    try {
      await streamProjectExploration(
        projectId,
        content,
        (chunk) => { setExploreStreaming((prev) => (prev ?? '') + chunk) },
        controller.signal,
      )
    } catch (err) {
      if (controller.signal.aborted) return
      notify('error', err instanceof Error ? err.message : '发送失败')
    } finally {
      setExploreStreaming((prev) => {
        if (prev) {
          setExploreMessages((msgs) => [...msgs, { id: `a_${Date.now()}`, role: 'assistant', content: prev }])
        }
        return null
      })
      setExploreSending(false)
    }
  }, [exploreInput, exploreSending, projectId, notify])

  if (isLoading || !project) {
    return <div className="py-8 text-center text-sm text-[var(--color-text-secondary)]">加载中...</div>
  }

  const currentStageIdx = STAGES.findIndex((s) => s.status === project.status)
  const isTerminal = ['completed', 'failed', 'canceled'].includes(project.status)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">
          &larr; 返回列表
        </button>
        <h2 className="text-lg font-semibold text-[var(--color-text)]">{project.title}</h2>
        <span className="rounded-full bg-[var(--color-bg-tertiary)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]">
          {STATUS_LABELS[project.status] ?? project.status}
        </span>
      </div>

      <p className="text-sm text-[var(--color-text-secondary)]">{project.research_question}</p>

      {/* Stage progress bar */}
      <div className="flex items-center gap-2">
        {STAGES.map((stage, i) => {
          const isActive = i === currentStageIdx
          const isDone = i < currentStageIdx || isTerminal
          return (
            <div key={stage.key} className="flex items-center gap-1">
              <div className={`flex h-7 items-center rounded-full px-2.5 text-[10px] font-medium ${
                isActive ? 'bg-[var(--color-primary)] text-white'
                  : isDone ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]'
                  : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)]'
              }`}>
                {stage.label}
              </div>
              {i < STAGES.length - 1 && (
                <div className="h-px w-4" style={{ backgroundColor: isDone ? 'var(--color-primary)' : 'var(--color-border)' }} />
              )}
            </div>
          )
        })}
      </div>

      {/* Stage content */}
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        {/* === Stage 1: Exploration === */}
        {project.status === 'exploring' && (
          <div className="flex h-[480px] flex-col">
            <h3 className="mb-2 text-sm font-medium text-[var(--color-text)]">探索阶段</h3>
            <p className="mb-3 text-xs text-[var(--color-text-secondary)]">
              向 AI 提问，分析数据可用性，推荐因子类别和标的范围。
            </p>
            {/* Messages */}
            <div ref={exploreScrollRef} className="flex-1 overflow-y-auto space-y-3 rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3">
              {exploreMessages.length === 0 && !exploreStreaming && (
                <div className="flex h-full items-center justify-center text-xs text-[var(--color-text-muted)]">
                  向 AI 助手提问，探索研究方向
                </div>
              )}
              {exploreMessages.map((msg) => (
                <div key={msg.id} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'assistant' && <Bot className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-primary)]" />}
                  <div className={`max-w-[85%] whitespace-pre-wrap rounded px-3 py-1.5 text-xs ${
                    msg.role === 'user' ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text)]'
                  }`}>
                    {msg.content}
                  </div>
                  {msg.role === 'user' && <User className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-text-secondary)]" />}
                </div>
              ))}
              {exploreStreaming && (
                <div className="flex gap-2">
                  <Bot className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-primary)]" />
                  <div className="max-w-[85%] whitespace-pre-wrap rounded bg-[var(--color-bg-tertiary)] px-3 py-1.5 text-xs text-[var(--color-text)]">
                    {exploreStreaming}
                  </div>
                </div>
              )}
              {exploreSending && !exploreStreaming && (
                <div className="flex gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-[var(--color-primary)]" />
                  <span className="text-xs text-[var(--color-text-muted)]">思考中...</span>
                </div>
              )}
            </div>
            {/* Input */}
            <div className="mt-2 flex gap-2">
              <input
                type="text"
                placeholder="描述研究方向或提问..."
                value={exploreInput}
                onChange={(e) => setExploreInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleExploreSend() } }}
                disabled={exploreSending}
                className="flex-1 rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-xs text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
              />
              <button
                onClick={handleExploreSend}
                disabled={exploreSending || !exploreInput.trim()}
                className="flex items-center rounded bg-[var(--color-primary)] px-3 py-1.5 text-white hover:opacity-90 disabled:opacity-50"
              >
                {exploreSending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>
        )}

        {/* === Stage 2: Hypothesis === */}
        {project.status === 'hypothesizing' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-[var(--color-text)]">假设管理</h3>
              <button
                onClick={() => createHypothesis.mutate({
                  projectId,
                  prediction: '新假设（请编辑）',
                  factor_names: project.instrument_ids.length > 0 ? [] : [],
                  created_by: 'human',
                })}
                disabled={createHypothesis.isPending}
                className="rounded bg-[var(--color-primary)] px-2 py-1 text-[10px] text-white hover:opacity-90 disabled:opacity-50"
              >
                手动创建假设
              </button>
            </div>
            {hypotheses.length === 0 ? (
              <p className="text-xs text-[var(--color-text-secondary)]">暂无假设。手动创建或推进到下一阶段前需至少1个已接受假设。</p>
            ) : (
              <div className="space-y-2">
                {hypotheses.map((hyp) => (
                  <HypothesisRow key={hyp.hypothesis_id} hypothesis={hyp} onUpdate={updateHypothesis} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* === Stage 3: Design === */}
        {project.status === 'designing' && (
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-[var(--color-text)]">试验设计</h3>
            {governanceStats && (
              <div className="flex gap-3 text-[10px] text-[var(--color-text-secondary)]">
                <span>调整后阈值: {governanceStats.adjusted_threshold.toFixed(4)}</span>
                <span>已用预算: {governanceStats.total_trials}/{governanceStats.budget_total}</span>
              </div>
            )}
            {/* Existing trial plans */}
            {trialPlans.length > 0 && (
              <div className="space-y-1">
                <span className="text-xs text-[var(--color-text-secondary)]">已设计试验:</span>
                {trialPlans.map((tp) => (
                  <div key={tp.trial_plan_id} className="flex items-center justify-between rounded border border-[var(--color-border)] px-3 py-1.5">
                    <div className="text-xs text-[var(--color-text)]">
                      试验#{tp.trial_index_in_project}: {tp.factor_combination.join(', ')} → {tp.metric_name}
                    </div>
                    <span className="text-[10px] text-[var(--color-text-secondary)]">α={tp.adjusted_alpha.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            )}
            {/* New trial plan form */}
            <div className="rounded border border-dashed border-[var(--color-border)] p-3">
              <span className="text-xs font-medium text-[var(--color-text)]">新建试验计划</span>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)]">假设</label>
                  <select
                    value={designForm.hypothesisId}
                    onChange={(e) => setDesignForm((f) => ({ ...f, hypothesisId: e.target.value }))}
                    className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]"
                  >
                    <option value="">选择假设</option>
                    {hypotheses.filter((h) => h.status === 'accepted').map((h) => (
                      <option key={h.hypothesis_id} value={h.hypothesis_id}>
                        {h.prediction.slice(0, 40)}...
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)]">因子组合 (逗号分隔)</label>
                  <input
                    value={designForm.factorCombination}
                    onChange={(e) => setDesignForm((f) => ({ ...f, factorCombination: e.target.value }))}
                    className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)]">标的 (逗号分隔)</label>
                  <input
                    value={designForm.instruments}
                    onChange={(e) => setDesignForm((f) => ({ ...f, instruments: e.target.value }))}
                    className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)]">评估指标</label>
                  <select
                    value={designForm.metricName}
                    onChange={(e) => setDesignForm((f) => ({ ...f, metricName: e.target.value }))}
                    className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]"
                  >
                    <option value="sharpe_ratio">Sharpe Ratio</option>
                    <option value="total_return">Total Return</option>
                    <option value="max_drawdown">Max Drawdown</option>
                    <option value="ic">Information Coefficient</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)]">训练期 开始</label>
                  <input type="date" value={designForm.trainStart}
                    onChange={(e) => setDesignForm((f) => ({ ...f, trainStart: e.target.value }))}
                    className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]" />
                </div>
                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)]">训练期 结束</label>
                  <input type="date" value={designForm.trainEnd}
                    onChange={(e) => setDesignForm((f) => ({ ...f, trainEnd: e.target.value }))}
                    className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]" />
                </div>
                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)]">测试期 开始</label>
                  <input type="date" value={designForm.testStart}
                    onChange={(e) => setDesignForm((f) => ({ ...f, testStart: e.target.value }))}
                    className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]" />
                </div>
                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)]">测试期 结束</label>
                  <input type="date" value={designForm.testEnd}
                    onChange={(e) => setDesignForm((f) => ({ ...f, testEnd: e.target.value }))}
                    className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]" />
                </div>
              </div>
              <div className="mt-2">
                <label className="text-[10px] text-[var(--color-text-secondary)]">预注册阈值</label>
                <input type="number" step="0.01" value={designForm.metricThreshold}
                  onChange={(e) => setDesignForm((f) => ({ ...f, metricThreshold: e.target.value }))}
                  className="ml-2 w-20 rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text)]" />
              </div>
              <button
                onClick={() => {
                  const fc = designForm.factorCombination.split(',').map((s) => s.trim()).filter(Boolean)
                  const inst = designForm.instruments.split(',').map((s) => s.trim()).filter(Boolean)
                  designTrialPlan.mutate({
                    hypothesisId: designForm.hypothesisId,
                    factor_combination: fc,
                    instruments: inst,
                    train_period_start: designForm.trainStart,
                    train_period_end: designForm.trainEnd,
                    test_period_start: designForm.testStart,
                    test_period_end: designForm.testEnd,
                    metric_name: designForm.metricName,
                    metric_threshold: parseFloat(designForm.metricThreshold) || 0,
                  })
                }}
                disabled={!designForm.hypothesisId || designTrialPlan.isPending}
                className="mt-2 rounded bg-[var(--color-primary)] px-3 py-1.5 text-xs text-white hover:opacity-90 disabled:opacity-50"
              >
                {designTrialPlan.isPending ? '创建中...' : '创建试验计划'}
              </button>
            </div>
          </div>
        )}

        {/* === Stage 4: Execution === */}
        {project.status === 'executing' && (
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-[var(--color-text)]">试验执行</h3>
            {trialPlans.length === 0 ? (
              <p className="text-xs text-[var(--color-text-secondary)]">无已设计试验。</p>
            ) : (
              <div className="space-y-2">
                {trialPlans.map((tp) => (
                  <div key={tp.trial_plan_id} className="flex items-center justify-between rounded border border-[var(--color-border)] p-3">
                    <div className="text-xs text-[var(--color-text)]">
                      <div className="font-medium">试验#{tp.trial_index_in_project}: {tp.factor_combination.join(', ')}</div>
                      <div className="mt-0.5 text-[10px] text-[var(--color-text-secondary)]">
                        {tp.train_period_start}~{tp.train_period_end} → {tp.test_period_start}~{tp.test_period_end}
                        {' '}| {tp.metric_name} α={tp.adjusted_alpha.toFixed(4)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {tp.status === 'planned' && (
                        <button
                          onClick={() => executeTrial.mutate(tp.trial_plan_id)}
                          disabled={executeTrial.isPending}
                          className="flex items-center gap-1 rounded bg-[var(--color-primary)] px-2 py-1 text-[10px] text-white hover:opacity-90 disabled:opacity-50"
                        >
                          <Play className="h-3 w-3" /> {executeTrial.isPending ? '执行中...' : '执行'}
                        </button>
                      )}
                      {tp.status === 'running' && (
                        <span className="flex items-center gap-1 text-[10px] text-[var(--color-primary)]">
                          <Loader2 className="h-3 w-3 animate-spin" /> 运行中
                        </span>
                      )}
                      {tp.status === 'completed' && (
                        <span className="flex items-center gap-1 text-[10px] text-green-600">
                          <CheckCircle className="h-3 w-3" /> 已完成
                        </span>
                      )}
                      {tp.status === 'failed' && (
                        <span className="flex items-center gap-1 text-[10px] text-red-600">
                          <XCircle className="h-3 w-3" /> 失败
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* === Stage 5: Validation === */}
        {project.status === 'validating' && (
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-[var(--color-text)]">结果验证</h3>
            {governanceStats && (
              <div className="grid grid-cols-4 gap-2">
                <StatCard label="总试验" value={governanceStats.total_trials} />
                <StatCard label="显著" value={governanceStats.significant_count} sub={`FWER ${governanceStats.family_wise_error_rate.toFixed(3)}`} />
                <StatCard label="拒绝" value={governanceStats.rejected_count} sub={`FDR ${governanceStats.false_discovery_rate.toFixed(3)}`} />
                <StatCard label="校正阈值" value={governanceStats.adjusted_threshold.toFixed(4)} />
              </div>
            )}
            {/* Trial results table */}
            {trialPlans.filter((tp) => tp.result).length > 0 && (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-[var(--color-text-secondary)]">
                    <th className="py-1 text-left">#</th>
                    <th className="text-left">因子</th>
                    <th className="text-right">训练</th>
                    <th className="text-right">测试</th>
                    <th className="text-right">指标值</th>
                    <th className="text-right">显著性</th>
                  </tr>
                </thead>
                <tbody>
                  {trialPlans.filter((tp) => tp.result).map((tp) => (
                    <tr key={tp.trial_plan_id} className="border-b border-[var(--color-border)]">
                      <td className="py-1 text-[var(--color-text)]">{tp.trial_index_in_project}</td>
                      <td className="text-[var(--color-text)]">{tp.factor_combination.join(', ')}</td>
                      <td className="text-right text-[var(--color-text)]">{tp.result!.train_metric?.toFixed(3) ?? '-'}</td>
                      <td className="text-right text-[var(--color-text)]">{tp.result!.test_metric?.toFixed(3) ?? '-'}</td>
                      <td className="text-right text-[var(--color-text)]">{tp.result!.metric_value.toFixed(3)}</td>
                      <td className="text-right">
                        <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${
                          tp.result!.is_significant
                            ? 'bg-green-100 text-green-700'
                            : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)]'
                        }`}>
                          {tp.result!.is_significant ? '显著' : '不显著'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {/* Validate and rollback actions */}
            <div className="flex gap-2">
              {trialPlans.filter((tp) => tp.status === 'completed' && !tp.result?.is_significant).map((tp) => (
                <button key={tp.trial_plan_id}
                  onClick={() => validateTrial.mutate(tp.trial_plan_id)}
                  disabled={validateTrial.isPending}
                  className="flex items-center gap-1 rounded bg-[var(--color-primary)] px-2 py-1 text-[10px] text-white hover:opacity-90 disabled:opacity-50"
                >
                  <Shield className="h-3 w-3" /> 验证试验#{tp.trial_index_in_project}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* === Stage 6: Report === */}
        {project.status === 'reporting' && (
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-[var(--color-text)]">研究报告</h3>
            {/* Provenance chain */}
            <div className="rounded border border-[var(--color-border)] p-3">
              <span className="text-xs font-medium text-[var(--color-text)]">溯源链</span>
              <div className="mt-2 flex items-center gap-1 text-[10px]">
                <span className="rounded bg-[var(--color-primary)]/20 px-2 py-0.5 text-[var(--color-primary)]">
                  项目: {project.title.slice(0, 20)}
                </span>
                <span className="text-[var(--color-text-muted)]">→</span>
                <span className="rounded bg-purple-100 px-2 py-0.5 text-purple-700">
                  {hypotheses.length} 假设
                </span>
                <span className="text-[var(--color-text-muted)]">→</span>
                <span className="rounded bg-blue-100 px-2 py-0.5 text-blue-700">
                  {trialPlans.length} 试验
                </span>
                <span className="text-[var(--color-text-muted)]">→</span>
                <span className="rounded bg-green-100 px-2 py-0.5 text-green-700">
                  {trialPlans.filter((tp) => tp.result?.is_significant).length} 显著
                </span>
              </div>
            </div>
            {/* Hypothesis → Trial → Result chain detail */}
            {hypotheses.filter((h) => h.status === 'accepted' || h.status === 'validated').map((hyp) => {
              const relatedTrials = trialPlans.filter((tp) => tp.hypothesis_id === hyp.hypothesis_id)
              return (
                <div key={hyp.hypothesis_id} className="rounded border border-[var(--color-border)] p-3">
                  <div className="text-xs font-medium text-[var(--color-text)]">
                    假设: {hyp.prediction}
                  </div>
                  <div className="mt-1 text-[10px] text-[var(--color-text-secondary)]">
                    因子: {hyp.factor_names.join(', ')} | 预期: {hyp.expected_effect} | 置信度: {(hyp.confidence * 100).toFixed(0)}%
                  </div>
                  {relatedTrials.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {relatedTrials.map((tp) => (
                        <div key={tp.trial_plan_id} className="flex items-center justify-between rounded bg-[var(--color-bg-secondary)] px-2 py-1 text-[10px]">
                          <span className="text-[var(--color-text)]">试验#{tp.trial_index_in_project}: {tp.factor_combination.join(', ')}</span>
                          {tp.result && (
                            <span className={tp.result.is_significant ? 'text-green-600 font-medium' : 'text-[var(--color-text-secondary)]'}>
                              {tp.result.metric_value.toFixed(3)} {tp.result.is_significant ? '(显著)' : '(不显著)'}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
            {/* Summary */}
            {governanceStats && (
              <div className="rounded border border-[var(--color-border)] p-3">
                <span className="text-xs font-medium text-[var(--color-text)]">治理摘要</span>
                <div className="mt-1 grid grid-cols-2 gap-2 text-[10px] text-[var(--color-text-secondary)]">
                  <span>总试验: {governanceStats.total_trials}</span>
                  <span>显著: {governanceStats.significant_count}</span>
                  <span>FWER: {governanceStats.family_wise_error_rate.toFixed(4)}</span>
                  <span>FDR: {governanceStats.false_discovery_rate.toFixed(4)}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* === Terminal state === */}
        {isTerminal && (
          <div>
            <h3 className="text-sm font-medium text-[var(--color-text)]">{STATUS_LABELS[project.status]}</h3>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              项目已{STATUS_LABELS[project.status]}。假设: {project.hypothesis_ids?.length ?? 0}, 试验: {project.trial_ids?.length ?? 0}
            </p>
          </div>
        )}

        {/* Created state (not yet exploring) */}
        {project.status === 'created' && (
          <div>
            <h3 className="text-sm font-medium text-[var(--color-text)]">项目已创建</h3>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              点击「推进到下一阶段」开始探索阶段。
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      {!isTerminal && (
        <div className="flex gap-2">
          <button
            onClick={() => advanceStage.mutate(projectId)}
            disabled={advanceStage.isPending}
            className="rounded bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {advanceStage.isPending ? '处理中...' : '推进到下一阶段'}
          </button>
          {project.status === 'validating' && (
            <button
              onClick={() => rollbackProject.mutate(projectId)}
              disabled={rollbackProject.isPending}
              className="rounded border border-orange-400 px-4 py-2 text-sm text-orange-600 hover:bg-orange-50 disabled:opacity-50"
            >
              回退到执行阶段
            </button>
          )}
          <button
            onClick={() => { if (confirm('确定要取消此项目？')) cancelProject.mutate(projectId) }}
            className="rounded border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
          >
            取消项目
          </button>
        </div>
      )}
    </div>
  )
}

// Sub-components

function HypothesisRow({ hypothesis, onUpdate }: { hypothesis: Hypothesis; onUpdate: ReturnType<typeof useUpdateHypothesis> }) {
  return (
    <div className="rounded border border-[var(--color-border)] p-3">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-[var(--color-text)]">{hypothesis.prediction || '无预测'}</p>
          <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-[var(--color-text-secondary)]">
            <span>置信度: {(hypothesis.confidence * 100).toFixed(0)}%</span>
            <span>因子: {hypothesis.factor_names.join(', ') || '无'}</span>
            <span>预期: {hypothesis.expected_effect}</span>
            {hypothesis.expected_magnitude > 0 && <span>效应量: {hypothesis.expected_magnitude}</span>}
          </div>
          {hypothesis.ai_rationale && (
            <p className="mt-1 text-[10px] text-[var(--color-text-muted)] italic">{hypothesis.ai_rationale.slice(0, 100)}...</p>
          )}
        </div>
        {hypothesis.status === 'draft' && (
          <div className="flex gap-1">
            <button onClick={() => onUpdate.mutate({ hypothesisId: hypothesis.hypothesis_id, status: 'accepted' })}
              className="flex items-center gap-1 rounded bg-green-600 px-2 py-1 text-[10px] text-white hover:opacity-90">
              <CheckCircle className="h-3 w-3" /> 接受
            </button>
            <button onClick={() => onUpdate.mutate({ hypothesisId: hypothesis.hypothesis_id, status: 'rejected' })}
              className="flex items-center gap-1 rounded bg-red-600 px-2 py-1 text-[10px] text-white hover:opacity-90">
              <XCircle className="h-3 w-3" /> 拒绝
            </button>
          </div>
        )}
        {hypothesis.status === 'accepted' && (
          <span className="flex items-center gap-1 text-[10px] text-green-600"><CheckCircle className="h-3 w-3" /> 已接受</span>
        )}
        {hypothesis.status === 'rejected' && (
          <span className="flex items-center gap-1 text-[10px] text-red-600"><XCircle className="h-3 w-3" /> 已拒绝</span>
        )}
        {(hypothesis.status === 'validated') && (
          <span className="flex items-center gap-1 text-[10px] text-blue-600"><Shield className="h-3 w-3" /> 已验证</span>
        )}
        {hypothesis.status === 'refuted' && (
          <span className="flex items-center gap-1 text-[10px] text-orange-600"><AlertTriangle className="h-3 w-3" /> 已驳斥</span>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded border border-[var(--color-border)] p-2 text-center">
      <div className="text-xs text-[var(--color-text-secondary)]">{label}</div>
      <div className="text-lg font-semibold text-[var(--color-text)]">{value}</div>
      {sub && <div className="text-[10px] text-[var(--color-text-muted)]">{sub}</div>}
    </div>
  )
}
