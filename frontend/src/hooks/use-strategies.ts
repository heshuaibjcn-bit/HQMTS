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
    queryFn: async () => {
      const result = await apiClient.get<{ strategies: Strategy[]; total: number }>('/strategies')
      return result.strategies ?? []
    },
  })
}

export function useStrategyInstances() {
  return useQuery({
    queryKey: ['strategies', 'instances'],
    queryFn: async () => {
      // Fetch all instances across strategies
      const strats = await apiClient.get<{ strategies: { strategy_id: string }[]; total: number }>('/strategies')
      const all: StrategyInstance[] = []
      for (const s of strats.strategies ?? []) {
        try {
          const res = await apiClient.get<{ instances: StrategyInstance[] }>(`/strategies/${s.strategy_id}/instances`)
          all.push(...(res.instances ?? []))
        } catch { /* skip */ }
      }
      return all
    },
  })
}
