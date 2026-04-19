import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useAuthStore } from '@/stores/auth-store'

// ── TypeScript interfaces ──────────────────────────────────────────────────────

export interface FactorInfo {
  name: string
  category: string
  version: string
  description: string
  params: Record<string, unknown>
}

export interface FactorValue {
  factor_name: string
  instrument_id: string
  value: number
  timestamp: string
  version: string
  metadata: Record<string, unknown>
}

export interface GovernanceStats {
  total_trials: number
  significant_count: number
  rejected_count: number
  family_wise_error_rate: number
  false_discovery_rate: number
  adjusted_threshold: number
  budget_remaining: number
  budget_total: number
}

export interface TrialRecord {
  trial_id: number
  factor_name: string
  strategy_name: string
  metric_name: string
  metric_value: number
  threshold: number
  is_significant: boolean
  notes: string
}

export interface ResearchReport {
  report_id: string
  title: string
  created_at: string
  factor_names: string[]
  instrument_ids: string[]
  time_range_days: number
  sections: ReportSection[]
}

export interface ReportSection {
  type: string
  title: string
  factors?: FactorInfo[]
  stats?: GovernanceStats
}

// ── Factor registry hooks ──────────────────────────────────────────────────────

export function useFactors(category?: string) {
  return useQuery({
    queryKey: ['factor-research', 'factors', category],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (category) params.category = category
      const result = await apiClient.get<{ factors: FactorInfo[]; total: number }>(
        '/factor-research/factors',
        params,
      )
      return result.factors
    },
  })
}

export function useFactorDetail(name: string) {
  return useQuery({
    queryKey: ['factor-research', 'factors', name],
    queryFn: () => apiClient.get<FactorInfo>(`/factor-research/factors/${name}`),
    enabled: !!name,
  })
}

// ── Factor computation hooks ───────────────────────────────────────────────────

export function useComputeFactors() {
  return useMutation({
    mutationFn: (params: {
      instrument_ids: string[]
      factor_names: string[]
      cycle: string
      start_date: string
      end_date: string
    }) => apiClient.post<{ values: FactorValue[]; count: number }>('/factor-research/compute', params),
  })
}

export function useCorrelationMatrix() {
  return useMutation({
    mutationFn: (params: {
      instrument_id: string
      factor_names: string[]
      cycle: string
      start_date: string
      end_date: string
    }) =>
      apiClient.post<{ matrix: (number | null)[][]; factors: string[] }>(
        '/factor-research/correlations',
        params,
      ),
  })
}

// ── Governance hooks ───────────────────────────────────────────────────────────

export function useGovernanceStats() {
  return useQuery({
    queryKey: ['factor-research', 'governance', 'stats'],
    queryFn: () => apiClient.get<GovernanceStats>('/factor-research/governance/stats'),
  })
}

export function useGovernanceTrials(factorName?: string) {
  return useQuery({
    queryKey: ['factor-research', 'governance', 'trials', factorName],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (factorName) params.factor_name = factorName
      const result = await apiClient.get<{ trials: TrialRecord[]; total: number }>(
        '/factor-research/governance/trials',
        params,
      )
      return result.trials
    },
  })
}

// ── Research task hooks ────────────────────────────────────────────────────────

export function useStartResearchTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      task_type: string
      instruments: string[]
      factors: string[]
      time_range_days?: number
      notes?: string
    }) => apiClient.post<{ task_id: string; status: string; trial_id: number }>('/factor-research/agent/research-task', params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'governance'] })
    },
  })
}

// ── Report hooks ───────────────────────────────────────────────────────────────

export function useGenerateReport() {
  return useMutation({
    mutationFn: (params: {
      title: string
      factor_names: string[]
      instrument_ids: string[]
      time_range_days?: number
      include_governance?: boolean
    }) => apiClient.post<ResearchReport>('/factor-research/reports', params),
  })
}

export function useResearchReport(reportId: string) {
  return useQuery({
    queryKey: ['factor-research', 'reports', reportId],
    queryFn: () => apiClient.get<ResearchReport>(`/factor-research/reports/${reportId}`),
    enabled: !!reportId,
  })
}

// ── SSE streaming for AI research chat ─────────────────────────────────────────

const SSE_IDLE_TIMEOUT_MS = 30_000

export async function streamResearchMessage(
  message: string,
  context: Record<string, unknown> | undefined,
  onChunk: (chunk: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let token = useAuthStore.getState().token
  if (!token) {
    const refreshed = await apiClient.tryRefresh()
    if (!refreshed) {
      useAuthStore.getState().logout()
      throw new Error('Session expired')
    }
    token = useAuthStore.getState().token
  }

  const response = await fetch('/factor-research/agent/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, context }),
    signal,
  })

  if (response.status === 401) {
    const refreshed = await apiClient.tryRefresh()
    if (!refreshed) {
      useAuthStore.getState().logout()
      throw new Error('Session expired. Please retry.')
    }
    throw new Error('Session expired. Please retry.')
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail || `HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let lastActivity = Date.now()

  try {
    while (true) {
      if (signal?.aborted) throw new Error('Aborted')

      if (Date.now() - lastActivity > SSE_IDLE_TIMEOUT_MS) {
        throw new Error('Research chat response timed out')
      }

      const readPromise = reader.read()
      const timeoutPromise = new Promise<{ done: boolean; value?: undefined }>(
        (resolve) => setTimeout(() => resolve({ done: false }), 5_000),
      )

      const result = await Promise.race([readPromise, timeoutPromise])

      if (result.done) break
      if (!result.value) continue

      lastActivity = Date.now()
      buffer += decoder.decode(result.value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try {
            const parsed = JSON.parse(data)
            if (parsed.type === 'content' && parsed.content) {
              onChunk(parsed.content)
            }
          } catch {
            // skip malformed chunks
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}


// ═══════════════════════════════════════════════════════════════════════════════
// Research Project Workflow (FR-RES-006~013)
// ═══════════════════════════════════════════════════════════════════════════════

export interface ResearchProject {
  research_project_id: string
  title: string
  research_question: string
  status: string
  current_stage: string
  instrument_ids: string[]
  factor_categories: string[]
  time_range_start: string
  time_range_end: string
  cycle: string
  governance_session_id: string
  agent_task_id: string | null
  trial_budget: number
  hypothesis_ids: string[]
  trial_ids: string[]
  report_id: string | null
  created_by: string
  mode: string
  created_at: string
  updated_at: string
}

export interface Hypothesis {
  hypothesis_id: string
  research_project_id: string
  version: number
  prediction: string
  factor_names: string[]
  target_metric: string
  expected_effect: string
  expected_magnitude: number
  instrument_scope: string[]
  market_regime: string | null
  time_period: string | null
  ai_rationale: string
  human_rationale: string
  supporting_evidence: string
  confidence: number
  priority: number
  status: string
  created_at: string
  created_by: string
}

export interface TrialPlan {
  trial_plan_id: string
  research_project_id: string
  hypothesis_id: string
  factor_combination: string[]
  instruments: string[]
  train_period_start: string
  train_period_end: string
  test_period_start: string
  test_period_end: string
  metric_name: string
  metric_threshold: number
  trial_index_in_project: number
  adjusted_alpha: number
  status: string
  result: TrialResult | null
  created_at: string
}

export interface TrialResult {
  metric_value: number
  metric_name: string
  is_significant: boolean
  adjusted_threshold: number
  raw_threshold: number
  sample_size: number
  train_metric: number | null
  test_metric: number | null
  notes: string
}

// ── Project hooks ─────────────────────────────────────────────────────────────

export function useResearchProjects(status?: string) {
  return useQuery({
    queryKey: ['factor-research', 'projects', status],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (status) params.status = status
      return apiClient.get<{ projects: ResearchProject[]; total: number }>(
        '/factor-research/projects',
        params,
      )
    },
  })
}

export function useResearchProject(projectId: string) {
  return useQuery({
    queryKey: ['factor-research', 'projects', projectId],
    queryFn: () =>
      apiClient.get<ResearchProject & { hypotheses: Hypothesis[]; trial_plans: TrialPlan[] }>(
        `/factor-research/projects/${projectId}`,
      ),
    enabled: !!projectId,
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      title: string
      research_question: string
      instrument_ids?: string[]
      factor_categories?: string[]
      time_range_start?: string
      time_range_end?: string
      cycle?: string
      trial_budget?: number
      mode?: string
    }) => apiClient.post<ResearchProject>('/factor-research/projects', params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects'] })
    },
  })
}

export function useAdvanceProjectStage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (projectId: string) =>
      apiClient.post<ResearchProject>(`/factor-research/projects/${projectId}/advance`),
    onSuccess: (_data, projectId) => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects', projectId] })
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects'] })
    },
  })
}

export function useCancelProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (projectId: string) =>
      apiClient.post<ResearchProject>(`/factor-research/projects/${projectId}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects'] })
    },
  })
}

export function useRollbackProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (projectId: string) =>
      apiClient.post<ResearchProject>(`/factor-research/projects/${projectId}/rollback`),
    onSuccess: (_data, projectId) => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects', projectId] })
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects'] })
    },
  })
}

// ── Hypothesis hooks ──────────────────────────────────────────────────────────

export function useProjectHypotheses(projectId: string) {
  return useQuery({
    queryKey: ['factor-research', 'projects', projectId, 'hypotheses'],
    queryFn: () =>
      apiClient.get<{ hypotheses: Hypothesis[]; total: number }>(
        `/factor-research/projects/${projectId}/hypotheses`,
      ),
    enabled: !!projectId,
  })
}

export function useCreateHypothesis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      projectId: string
      prediction?: string
      factor_names?: string[]
      target_metric?: string
      expected_effect?: string
      expected_magnitude?: number
      instrument_scope?: string[]
      ai_rationale?: string
      confidence?: number
      created_by?: string
    }) =>
      apiClient.post<Hypothesis>(
        `/factor-research/projects/${params.projectId}/hypotheses`,
        params,
      ),
    onSuccess: (_data, params) => {
      queryClient.invalidateQueries({
        queryKey: ['factor-research', 'projects', params.projectId, 'hypotheses'],
      })
    },
  })
}

export function useUpdateHypothesis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      hypothesisId: string
      status: string
      human_rationale?: string
    }) =>
      apiClient.patch<Hypothesis>(
        `/factor-research/hypotheses/${params.hypothesisId}`,
        params,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects'] })
    },
  })
}

// ── Trial plan hooks ─────────────────────────────────────────────────────────

export function useDesignTrialPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      hypothesisId: string
      factor_combination?: string[]
      instruments?: string[]
      train_period_start?: string
      train_period_end?: string
      test_period_start?: string
      test_period_end?: string
      metric_name?: string
      metric_threshold?: number
    }) =>
      apiClient.post<TrialPlan>(
        `/factor-research/hypotheses/${params.hypothesisId}/trial-plan`,
        {
          hypothesis_id: params.hypothesisId,
          factor_combination: params.factor_combination,
          instruments: params.instruments,
          train_period_start: params.train_period_start,
          train_period_end: params.train_period_end,
          test_period_start: params.test_period_start,
          test_period_end: params.test_period_end,
          metric_name: params.metric_name,
          metric_threshold: params.metric_threshold,
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects'] })
    },
  })
}

export function useExecuteTrial() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (trialPlanId: string) =>
      apiClient.post<TrialResult>(`/factor-research/trial-plans/${trialPlanId}/execute`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects'] })
    },
  })
}

export function useValidateTrial() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (trialPlanId: string) =>
      apiClient.post<{ trial_plan_id: string; status: string; governance: GovernanceStats }>(
        `/factor-research/trial-plans/${trialPlanId}/validate`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'projects'] })
    },
  })
}

// ── Project-scoped governance ─────────────────────────────────────────────────

export function useProjectGovernance(projectId: string) {
  return useQuery({
    queryKey: ['factor-research', 'projects', projectId, 'governance'],
    queryFn: () =>
      apiClient.get<GovernanceStats>(`/factor-research/projects/${projectId}/governance`),
    enabled: !!projectId,
  })
}

// ── Project-scoped exploration SSE ────────────────────────────────────────────

export async function streamProjectExploration(
  projectId: string,
  message: string,
  onChunk: (chunk: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let token = useAuthStore.getState().token
  if (!token) {
    const refreshed = await apiClient.tryRefresh()
    if (!refreshed) {
      useAuthStore.getState().logout()
      throw new Error('Session expired')
    }
    token = useAuthStore.getState().token
  }

  const response = await fetch(`/factor-research/projects/${projectId}/explore`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message }),
    signal,
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail || `HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let lastActivity = Date.now()

  try {
    while (true) {
      if (signal?.aborted) throw new Error('Aborted')
      if (Date.now() - lastActivity > SSE_IDLE_TIMEOUT_MS) {
        throw new Error('Response timed out')
      }

      const result = await Promise.race([
        reader.read(),
        new Promise<{ done: boolean; value?: undefined }>((resolve) =>
          setTimeout(() => resolve({ done: false }), 5_000),
        ),
      ])

      if (result.done) break
      if (!result.value) continue

      lastActivity = Date.now()
      buffer += decoder.decode(result.value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try {
            const parsed = JSON.parse(data)
            if (parsed.type === 'content' && parsed.content) {
              onChunk(parsed.content)
            }
          } catch {
            // skip
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}


// ═══════════════════════════════════════════════════════════════════════════════
// Autonomous Research Cycles (FR-RES-014~020, FR-STR-006~012)
// ═══════════════════════════════════════════════════════════════════════════════

export interface ResearchCycle {
  research_cycle_id: string
  title: string
  opportunity_type: string
  opportunity_signal: Record<string, unknown>
  status: string
  research_project_id: string | null
  budget: { max_trials: number; max_llm_calls: number; max_backtests: number; max_duration_hours: number }
  budget_consumed: { trials: number; llm_calls: number; backtests: number }
  factor_discovery_ids: string[]
  strategy_candidate_ids: string[]
  autonomy_level: string
  cycle_outcome: string | null
  outcome_reason: string
  source_strategy_instance_id: string
  triggered_by: string
  agent_task_id: string | null
  created_at: string
  updated_at: string
  discoveries?: FactorDiscoveryItem[]
  candidates?: StrategyCandidateItem[]
}

export interface FactorDiscoveryItem {
  factor_discovery_id: string
  research_cycle_id: string
  research_project_id: string
  factor_names: string[]
  factor_combination: string
  discovery_type: string
  description: string
  hypothesis_id: string | null
  trial_plan_id: string | null
  metric_value: number
  adjusted_alpha: number
  is_significant: boolean
  confidence: number
  market_regime: string
  instrument_scope: string[]
  status: string
  created_at: string
}

export interface StrategyCandidateItem {
  strategy_candidate_id: string
  research_cycle_id: string
  factor_discovery_ids: string[]
  source_factors: string[]
  strategy_template_name: string
  strategy_params: Record<string, unknown>
  param_ranges: Record<string, unknown>
  ai_rationale: string
  signal_logic_description: string
  status: string
  backtest_sharpe: number | null
  backtest_return: number | null
  backtest_drawdown: number | null
  backtest_trades: number | null
  evaluation_score: number | null
  evaluation_verdict: string | null
  created_at: string
}

// ── Cycle hooks ─────────────────────────────────────────────────────────────

export function useResearchCycles(status?: string) {
  return useQuery({
    queryKey: ['factor-research', 'cycles', status],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (status) params.status = status
      return apiClient.get<{ cycles: ResearchCycle[]; total: number }>(
        '/factor-research/cycles',
        params,
      )
    },
  })
}

export function useResearchCycle(cycleId: string) {
  return useQuery({
    queryKey: ['factor-research', 'cycles', cycleId],
    queryFn: () =>
      apiClient.get<ResearchCycle>(`/factor-research/cycles/${cycleId}`),
    enabled: !!cycleId,
  })
}

export function useCreateCycle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      title: string
      opportunity_type?: string
      opportunity_signal_json?: Record<string, unknown>
      research_question?: string
      instrument_ids?: string[]
      factor_categories?: string[]
      autonomy_level?: string
    }) => apiClient.post<ResearchCycle>('/factor-research/cycles', params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'cycles'] })
    },
  })
}

export function useCancelCycle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (cycleId: string) =>
      apiClient.post<ResearchCycle>(`/factor-research/cycles/${cycleId}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'cycles'] })
    },
  })
}

// ── Discovery hooks ─────────────────────────────────────────────────────────

export function useCycleDiscoveries(cycleId: string) {
  return useQuery({
    queryKey: ['factor-research', 'cycles', cycleId, 'discoveries'],
    queryFn: () =>
      apiClient.get<{ discoveries: FactorDiscoveryItem[]; total: number }>(
        `/factor-research/cycles/${cycleId}/discoveries`,
      ),
    enabled: !!cycleId,
  })
}

// ── Candidate hooks ─────────────────────────────────────────────────────────

export function useCycleCandidates(cycleId: string) {
  return useQuery({
    queryKey: ['factor-research', 'cycles', cycleId, 'candidates'],
    queryFn: () =>
      apiClient.get<{ candidates: StrategyCandidateItem[]; total: number }>(
        `/factor-research/cycles/${cycleId}/candidates`,
      ),
    enabled: !!cycleId,
  })
}

export function useApproveCandidatePaper() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (candidateId: string) =>
      apiClient.post<StrategyCandidateItem>(
        `/factor-research/candidates/${candidateId}/approve-paper`,
        { notes: '' },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'cycles'] })
    },
  })
}

export function useRejectCandidate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (candidateId: string) =>
      apiClient.post<StrategyCandidateItem>(
        `/factor-research/candidates/${candidateId}/reject`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['factor-research', 'cycles'] })
    },
  })
}

// ── Decay monitor hook ──────────────────────────────────────────────────────

export function useDecayMonitorStatus() {
  return useQuery({
    queryKey: ['factor-research', 'decay-monitor'],
    queryFn: () =>
      apiClient.get<{
        status: string
        monitored_factors: number
        decayed_factors: number
        last_check: string
        triggered_cycles: string[]
      }>('/factor-research/decay-monitor/status'),
  })
}
