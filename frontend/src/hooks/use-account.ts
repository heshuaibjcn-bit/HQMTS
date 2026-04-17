import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface AccountSummary {
  total_assets: number
  available: number
  frozen: number
  market_value: number
  today_pnl: number
  today_pnl_pct: number
  position_count: number
  active_strategy_count: number
}

export function useAccountSummary() {
  return useQuery({
    queryKey: ['account', 'summary'],
    queryFn: () => apiClient.get<AccountSummary>('/account/summary'),
  })
}
