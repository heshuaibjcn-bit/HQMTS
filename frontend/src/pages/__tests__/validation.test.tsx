import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'

// Mock the validation hooks
const mockUseAdmissions = vi.fn()
const mockUseCreateAdmission = vi.fn()
const mockUseEvaluateReadiness = vi.fn()
const mockUseApproveAdmission = vi.fn()

vi.mock('@/hooks/use-validation', () => ({
  useAdmissions: () => mockUseAdmissions(),
  useCreateAdmission: () => mockUseCreateAdmission(),
  useEvaluateReadiness: () => mockUseEvaluateReadiness(),
  useApproveAdmission: () => mockUseApproveAdmission(),
}))

// Mock auth store
vi.mock('@/stores/auth-store', async () => {
  const { create } = await import('zustand')
  const useAuthStore = create(() => ({
    user: { user_id: 'test_user', username: 'tester' },
    token: 'test-token',
    isAuthenticated: true,
  }))
  return { useAuthStore }
})

// Mock notification store
vi.mock('@/stores/notification-store', async () => {
  const { create } = await import('zustand')
  const addNotification = vi.fn()
  const useNotificationStore = create(() => ({
    notifications: [],
    addNotification,
    removeNotification: vi.fn(),
  }))
  return { useNotificationStore }
})

vi.mock('@/components/shared/lifecycle-breadcrumb', () => ({
  LifecycleBreadcrumb: () => <span>breadcrumb</span>,
}))

import { ValidationPage } from '../research/validation'
import { useNotificationStore } from '@/stores/notification-store'

const defaultMutations = {
  mutateAsync: vi.fn(),
  mutate: vi.fn(),
  isPending: false,
  isSuccess: false,
  isError: false,
  data: undefined,
  error: null,
  reset: vi.fn(),
}

function setupMocks(overrides: Record<string, Partial<ReturnType<typeof Object>>> = {}) {
  mockUseAdmissions.mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    ...overrides.admissions,
  })
  mockUseCreateAdmission.mockReturnValue({
    ...defaultMutations,
    ...overrides.createAdmission,
  })
  mockUseEvaluateReadiness.mockReturnValue({
    ...defaultMutations,
    ...overrides.evaluateReadiness,
  })
  mockUseApproveAdmission.mockReturnValue({
    ...defaultMutations,
    ...overrides.approveAdmission,
  })
}

describe('ValidationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  describe('rendering', () => {
    it('renders page title', () => {
      renderWithProviders(<ValidationPage />)
      expect(screen.getByText('策略验证')).toBeInTheDocument()
    })

    it('renders create button', () => {
      renderWithProviders(<ValidationPage />)
      expect(screen.getByText('创建验证')).toBeInTheDocument()
    })

    it('shows loading state', () => {
      setupMocks({ admissions: { isLoading: true } })
      renderWithProviders(<ValidationPage />)
      expect(screen.getByText('加载中...')).toBeInTheDocument()
    })

    it('shows empty state when no admissions', () => {
      setupMocks({ admissions: { data: [], isLoading: false } })
      renderWithProviders(<ValidationPage />)
      expect(screen.getByText(/暂无验证记录/)).toBeInTheDocument()
    })
  })

  describe('error states', () => {
    it('shows error state when API fails', () => {
      setupMocks({ admissions: { isError: true, refetch: vi.fn() } })
      renderWithProviders(<ValidationPage />)
      expect(screen.getByText('加载验证记录失败')).toBeInTheDocument()
      expect(screen.getByText('重试')).toBeInTheDocument()
    })

    it('calls refetch when retry clicked', async () => {
      const refetch = vi.fn()
      setupMocks({ admissions: { isError: true, refetch } })
      const user = userEvent.setup()
      renderWithProviders(<ValidationPage />)
      await user.click(screen.getByText('重试'))
      expect(refetch).toHaveBeenCalled()
    })
  })

  describe('create admission', () => {
    it('shows create form when button clicked', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ValidationPage />)
      await user.click(screen.getByText('创建验证'))
      expect(screen.getByPlaceholderText('策略实例 ID')).toBeInTheDocument()
    })

    it('shows toast on create failure', async () => {
      const mutateAsync = vi.fn().mockRejectedValue(new Error('Network error'))
      setupMocks({ createAdmission: { mutateAsync } })
      const user = userEvent.setup()
      renderWithProviders(<ValidationPage />)
      await user.click(screen.getByText('创建验证'))
      await user.type(screen.getByPlaceholderText('策略实例 ID'), 'inst-001')
      await user.click(screen.getByText('提交'))
      await waitFor(() => {
        expect(useNotificationStore.getState().addNotification).toHaveBeenCalledWith('error', expect.stringContaining('失败'))
      })
    })

    it('disables submit button while pending', async () => {
      let resolveMutate: () => void
      const mutateAsync = vi.fn().mockImplementation(() => new Promise<void>((r) => { resolveMutate = r }))
      setupMocks({ createAdmission: { mutateAsync, isPending: true } })
      const user = userEvent.setup()
      renderWithProviders(<ValidationPage />)
      await user.click(screen.getByText('创建验证'))
      await user.type(screen.getByPlaceholderText('策略实例 ID'), 'inst-001')
      const submitBtn = screen.getByText('提交')
      expect(submitBtn).toBeDisabled()
    })
  })

  describe('approval', () => {
    it('shows toast when user is null', async () => {
      // Override auth store to return null user
      const { useAuthStore } = await import('@/stores/auth-store')
      useAuthStore.setState({ user: null })

      const data = [{
        admission_id: 'adm-001',
        strategy_instance_id: 'inst-001',
        strategy_version: '1.0',
        status: 'pending_review',
        paper_sharpe_ratio: null,
        paper_trading_days: null,
        readiness_score: null,
        readiness_passed: null,
        approver: null,
        decision_reason: null,
        created_at: '2026-01-01',
        decided_at: null,
      }]
      setupMocks({ admissions: { data, isLoading: false } })

      const user = userEvent.setup()
      renderWithProviders(<ValidationPage />)
      await user.click(screen.getByText('批准'))
      await user.click(screen.getByText('确认批准'))
      await waitFor(() => {
        expect(useNotificationStore.getState().addNotification).toHaveBeenCalledWith('error', '请重新登录')
      })
    })

    it('disables confirm button while pending', async () => {
      const data = [{
        admission_id: 'adm-001',
        strategy_instance_id: 'inst-001',
        strategy_version: '1.0',
        status: 'pending_review',
        paper_sharpe_ratio: null,
        paper_trading_days: null,
        readiness_score: null,
        readiness_passed: null,
        approver: null,
        decision_reason: null,
        created_at: '2026-01-01',
        decided_at: null,
      }]
      setupMocks({
        admissions: { data, isLoading: false },
        approveAdmission: { isPending: true, mutateAsync: vi.fn() },
      })

      const user = userEvent.setup()
      renderWithProviders(<ValidationPage />)
      await user.click(screen.getByText('批准'))
      // Confirm button should be disabled when isPending
      expect(screen.getByText('确认批准')).toBeDisabled()
    })
  })
})
