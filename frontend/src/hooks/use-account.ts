import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface AccountSummary {
  total_asset: number
  available_cash: number
  frozen_cash: number
  market_value: number
  pnl_intraday: number
  drawdown_intraday: number
  positions_count: number
  active_strategies: number
  risk_status: string
}

export function useAccountSummary() {
  return useQuery({
    queryKey: ['account', 'summary'],
    queryFn: () => apiClient.get<AccountSummary>('/account/summary'),
  })
}
