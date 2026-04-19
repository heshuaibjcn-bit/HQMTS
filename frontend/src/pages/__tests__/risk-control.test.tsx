import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'

// Mock hooks
const mockUseQuery = vi.fn()
vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (...args: unknown[]) => mockUseQuery(...args),
  }
})

const mockUseAlerts = vi.fn()
vi.mock('@/hooks/use-alerts', () => ({
  useAlerts: () => mockUseAlerts(),
}))

vi.mock('@/components/risk/risk-layers-card', () => ({
  RiskLayersCard: () => <div data-testid="risk-layers">Risk Layers</div>,
}))
vi.mock('@/components/risk/kill-switch-panel', () => ({
  KillSwitchPanel: () => <div data-testid="kill-switch">Kill Switch</div>,
}))
vi.mock('@/components/risk/force-flatten-panel', () => ({
  ForceFlattenPanel: () => <div data-testid="force-flatten">Force Flatten</div>,
}))

import { RiskControlPage } from '../trading/risk-control'

function setupMocks(overrides: Record<string, Partial<ReturnType<typeof Object>>> = {}) {
  mockUseQuery.mockReturnValue({
    data: null,
    isLoading: true,
    isError: false,
    refetch: vi.fn(),
    ...overrides.health,
  })
  mockUseAlerts.mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    ...overrides.alerts,
  })
}

describe('RiskControlPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  describe('rendering', () => {
    it('renders page title', () => {
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('风控中心')).toBeInTheDocument()
    })

    it('renders risk components', () => {
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByTestId('risk-layers')).toBeInTheDocument()
      expect(screen.getByTestId('kill-switch')).toBeInTheDocument()
      expect(screen.getByTestId('force-flatten')).toBeInTheDocument()
    })

    it('renders health section header', () => {
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('系统状态')).toBeInTheDocument()
    })

    it('renders alerts section header', () => {
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('告警')).toBeInTheDocument()
    })
  })

  describe('health data', () => {
    it('shows loading skeleton when loading', () => {
      setupMocks({ health: { isLoading: true } })
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('QMT')).toBeInTheDocument()
    })

    it('shows health data when loaded', () => {
      setupMocks({
        health: {
          isLoading: false,
          isError: false,
          data: {
            qmt: { connected: true, latency_ms: 12 },
            data_source: { connected: true, latency_ms: 5 },
            bar_aggregation: { status: 'normal', last_bar_time: null },
            agent: { status: 'running', active_tasks: 3 },
          },
        },
      })
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('12ms')).toBeInTheDocument()
      expect(screen.getByText('3 任务')).toBeInTheDocument()
    })

    it('shows error state when health API fails', () => {
      setupMocks({ health: { isError: true, isLoading: false, refetch: vi.fn() } })
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('无法获取系统状态')).toBeInTheDocument()
      expect(screen.getByText('重试')).toBeInTheDocument()
    })

    it('calls refetch on retry click', async () => {
      const refetch = vi.fn()
      setupMocks({ health: { isError: true, isLoading: false, refetch } })
      const user = userEvent.setup()
      renderWithProviders(<RiskControlPage />)
      await user.click(screen.getByText('重试'))
      expect(refetch).toHaveBeenCalled()
    })
  })

  describe('alerts', () => {
    it('shows empty state when no alerts', () => {
      setupMocks({ alerts: { data: [], isError: false } })
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('暂无告警')).toBeInTheDocument()
    })

    it('shows error state when alerts API fails', () => {
      setupMocks({ alerts: { isError: true } })
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('无法获取告警')).toBeInTheDocument()
    })

    it('shows P0/P1 badge count', () => {
      setupMocks({
        alerts: {
          data: [
            { alert_id: 'a1', level: 'P0', message: 'critical', detected_at: '2026-01-01' },
            { alert_id: 'a2', level: 'P1', message: 'warning', detected_at: '2026-01-01' },
            { alert_id: 'a3', level: 'P2', message: 'info', detected_at: '2026-01-01' },
          ],
          isError: false,
        },
      })
      renderWithProviders(<RiskControlPage />)
      expect(screen.getByText('2 紧急')).toBeInTheDocument()
    })
  })
})
