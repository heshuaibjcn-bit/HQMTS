import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface Signal {
  signal_id: string
  strategy_id: string
  strategy_name: string
  instrument_code: string
  direction: 'buy' | 'sell'
  strength: number
  price_target: number
  created_at: string
}

export interface SignalFilters {
  strategy_id?: string
  instrument_code?: string
  limit?: number
}

export function useSignals(filters?: SignalFilters) {
  return useQuery({
    queryKey: ['signals', filters],
    queryFn: () =>
      apiClient.get<Signal[]>('/signals', filters as Record<string, string>),
  })
}
