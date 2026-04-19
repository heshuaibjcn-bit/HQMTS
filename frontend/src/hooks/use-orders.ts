import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface Order {
  order_id: string
  instrument_code: string
  instrument_name: string
  direction: 'buy' | 'sell'
  order_type: string
  price: number
  quantity: number
  filled_quantity: number
  status: string
  created_at: string
  updated_at: string
}

export interface OrderFilters {
  status?: string
  instrument_code?: string
  limit?: number
}

export function useOrders(filters?: OrderFilters) {
  return useQuery({
    queryKey: ['orders', filters],
    queryFn: async () => {
      const result = await apiClient.get<{ orders: Order[] }>('/orders', filters as Record<string, string>)
      return result.orders ?? []
    },
  })
}

export function useCancelOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (orderId: string) =>
      apiClient.post(`/orders/${orderId}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}
