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
    queryFn: () =>
      apiClient.get<Order[]>('/orders', filters as Record<string, string>),
  })
}

export function useCancelOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (orderId: string) =>
      apiClient.delete(`/orders/${orderId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}
