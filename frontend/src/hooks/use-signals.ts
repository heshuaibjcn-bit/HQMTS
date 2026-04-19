import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface Signal {
  signal_id: string
  strategy_id: string
  strategy_instance_id: string
  strategy_name: string
  instrument_id: string
  instrument_code: string
  direction: string
  strength: number
  price_target: number | null
  signal_type: string
  cycle: string
  decision_time: string
  valid_until: string
  created_at: string
}

export interface SignalFilters {
  strategy_instance_id?: string
  instrument_id?: string
  limit?: number
}

export function useSignals(filters?: SignalFilters) {
  return useQuery({
    queryKey: ['signals', filters],
    queryFn: async () => {
      const result = await apiClient.get<{ signals: Signal[]; total: number }>('/signals', filters as Record<string, string>)
      return result.signals ?? []
    },
  })
}
