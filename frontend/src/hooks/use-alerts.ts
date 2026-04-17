import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface Alert {
  alert_id: string
  rule_name: string
  level: 'P0' | 'P1' | 'P2' | 'P3'
  metric: string
  value: number
  threshold: number
  message: string
  acknowledged: boolean
  detected_at: string
}

export interface AlertFilters {
  level?: string
  acknowledged?: string
  limit?: number
}

export function useAlerts(filters?: AlertFilters) {
  return useQuery({
    queryKey: ['alerts', filters],
    queryFn: async () => {
      const result = await apiClient.get<{ alerts: Alert[]; total: number }>(
        '/alerts',
        filters as Record<string, string>,
      )
      return result.alerts
    },
  })
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (alertId: string) =>
      apiClient.post(`/alerts/${alertId}/acknowledge`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
    },
  })
}
