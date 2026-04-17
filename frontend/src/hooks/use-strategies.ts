import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface Strategy {
  strategy_id: string
  name: string
  type: string
  status: string
  created_at: string
  updated_at: string
}

export interface StrategyInstance {
  instance_id: string
  strategy_id: string
  strategy_name: string
  instrument_codes: string[]
  status: string
  started_at: string
  pnl: number
}

export function useStrategies() {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiClient.get<Strategy[]>('/strategies'),
  })
}

export function useStrategyInstances() {
  return useQuery({
    queryKey: ['strategies', 'instances'],
    queryFn: () => apiClient.get<StrategyInstance[]>('/strategies/instances'),
  })
}
