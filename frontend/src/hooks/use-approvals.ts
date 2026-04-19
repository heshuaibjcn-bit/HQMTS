import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface Approval {
  proposal_id: string
  title: string
  description: string
  proposed_by: string
  risk_level: string
  status: 'pending' | 'approved' | 'rejected' | 'expired'
  created_at: string
  expires_at: string
  actions: {
    approve: boolean
    reject: boolean
  }
}

export function usePendingApprovals() {
  return useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: () =>
      apiClient.get<Approval[]>('/api/approvals', { status: 'pending' }),
    refetchInterval: 10_000,
  })
}

export function useApproveProposal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      proposalId,
      note,
    }: {
      proposalId: string
      note?: string
    }) =>
      apiClient.post(`/api/approvals/${proposalId}/approve`, { note }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
  })
}

export function useRejectProposal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      proposalId,
      reason,
    }: {
      proposalId: string
      reason: string
    }) =>
      apiClient.post(`/api/approvals/${proposalId}/reject`, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
  })
}
