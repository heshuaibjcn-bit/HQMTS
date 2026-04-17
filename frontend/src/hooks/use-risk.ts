import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface RiskStatus {
  layers: {
    pre_trade: { status: string; checks_passed: number; checks_total: number }
    position: { status: string; checks_passed: number; checks_total: number }
    portfolio: { status: string; checks_passed: number; checks_total: number }
    capital: { status: string; checks_passed: number; checks_total: number }
    compliance: { status: string; checks_passed: number; checks_total: number }
  }
  kill_switch_active: boolean
}

export function useRiskStatus() {
  return useQuery({
    queryKey: ['risk', 'status'],
    queryFn: () => apiClient.get<RiskStatus>('/risk/status'),
  })
}

export function useActivateKillSwitch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post('/risk/kill-switch'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['risk'] })
    },
  })
}

export function useDeactivateKillSwitch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post('/risk/kill-switch/deactivate'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['risk'] })
    },
  })
}
