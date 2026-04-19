import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface Admission {
  admission_id: string
  strategy_instance_id: string
  strategy_version: string
  status: string
  paper_sharpe_ratio: number | null
  paper_trading_days: number | null
  readiness_score: number | null
  readiness_passed: boolean | null
  approver: string | null
  decision_reason: string | null
  created_at: string
  decided_at: string | null
}

export function useAdmissions() {
  return useQuery({
    queryKey: ['validation', 'admissions'],
    queryFn: async () => {
      const result = await apiClient.get<{ admissions: Admission[]; total: number }>('/validation/admissions')
      return result.admissions
    },
  })
}

export function useCreateAdmission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: { strategy_instance_id: string; strategy_version?: string }) =>
      apiClient.post<Admission>('/validation/admission', params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['validation'] })
    },
  })
}

export function useCollectMetrics() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      admission_id: string
      total_return_pct: number
      max_drawdown_pct: number
      sharpe_ratio: number
      win_rate_pct: number
      total_trades: number
      trading_days: number
      max_daily_loss_pct: number
    }) => {
      const { admission_id, ...body } = params
      return apiClient.post<Admission>(`/validation/admission/${admission_id}/metrics`, body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['validation'] })
    },
  })
}

export function useEvaluateReadiness() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (admission_id: string) =>
      apiClient.post<Admission>(`/validation/admission/${admission_id}/evaluate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['validation'] })
    },
  })
}

export function useApproveAdmission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: { admission_id: string; approver: string; decision: string; reason?: string }) => {
      const { admission_id, ...body } = params
      return apiClient.post<Admission>(`/validation/admission/${admission_id}/approve`, body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['validation'] })
    },
  })
}
