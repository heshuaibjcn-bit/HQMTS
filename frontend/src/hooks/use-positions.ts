import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface Position {
  position_id: string
  instrument_code: string
  instrument_name: string
  direction: 'long' | 'short'
  quantity: number
  available_quantity: number
  avg_cost: number
  market_value: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  is_t1: boolean
  updated_at: string
}

export function usePositions() {
  return useQuery({
    queryKey: ['positions'],
    queryFn: () => apiClient.get<Position[]>('/api/positions'),
  })
}
