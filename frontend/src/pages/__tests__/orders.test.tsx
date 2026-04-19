import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'

// Mock hooks
const mockUseOrders = vi.fn()
vi.mock('@/hooks/use-orders', () => ({
  useOrders: () => mockUseOrders(),
}))

// Mock order status badge
vi.mock('@/components/orders/order-status-badge', () => ({
  OrderStatusBadge: ({ status }: { status: string }) => <span>{status}</span>,
}))

// Mock dialog components
vi.mock('@/components/orders/order-detail-dialog', () => ({
  OrderDetailDialog: () => null,
}))
vi.mock('@/components/orders/cancel-order-dialog', () => ({
  CancelOrderDialog: () => null,
}))

import { OrdersPage } from '../trading/orders'

function setupMocks(overrides: Record<string, unknown> = {}) {
  mockUseOrders.mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    ...overrides.orders,
  })
}

describe('OrdersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  describe('rendering', () => {
    it('renders page title', () => {
      renderWithProviders(<OrdersPage />)
      expect(screen.getByText('订单')).toBeInTheDocument()
    })

    it('shows empty state when no orders', () => {
      renderWithProviders(<OrdersPage />)
      expect(screen.getByText('暂无订单')).toBeInTheDocument()
    })

    it('shows loading state', () => {
      setupMocks({ orders: { isLoading: true } })
      renderWithProviders(<OrdersPage />)
      expect(screen.getByText('加载中...')).toBeInTheDocument()
    })

    it('renders orders table when data present', () => {
      setupMocks({
        orders: {
          data: [{
            order_id: 'ord-001',
            strategy_id: 'strat-001',
            instrument_code: '000001.SZ',
            instrument_name: '平安银行',
            side: 'buy',
            direction: 'buy',
            order_type: 'limit',
            quantity: 100,
            price: 10.5,
            filled_quantity: 0,
            status: 'pending_submit',
            created_at: '2026-01-01T10:00:00',
            updated_at: '2026-01-01T10:00:00',
          }],
          isLoading: false,
        },
      })
      renderWithProviders(<OrdersPage />)
      expect(screen.getByText('000001.SZ')).toBeInTheDocument()
    })
  })

  describe('error states', () => {
    it('renders without crashing on error state', () => {
      setupMocks({ orders: { isError: true } })
      renderWithProviders(<OrdersPage />)
      expect(screen.getByText('订单')).toBeInTheDocument()
    })
  })
})
