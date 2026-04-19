import { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth-store'
import { useWSStatus } from '@/hooks/use-websocket'
import { ToastContainer } from '@/components/ui/toast'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { LoginPage } from '@/pages/login'
import { AppShell } from '@/components/layout/app-shell'

// Trading pages
import { TradingOverviewPage } from '@/pages/trading/trading-overview'
import { PositionsPage } from '@/pages/trading/positions'
import { OrdersPage } from '@/pages/trading/orders'
import { SignalsPage } from '@/pages/trading/signals'
import { StrategyInstancesPage } from '@/pages/trading/strategy-instances'
import { AuditPage } from '@/pages/trading/audit-trail'

// Research pages
import { StrategyDevPage } from '@/pages/research/strategy-dev'
import BacktestCenterPage from '@/pages/research/backtest-center'
import { FactorResearchPage } from '@/pages/research/factor-research'
import { ValidationPage } from '@/pages/research/validation'
import { OptimizationPage } from '@/pages/research/optimization'

// Knowledge pages
import { ChatPage } from '@/pages/knowledge/chat'
import { StrategyDocsPage } from '@/pages/knowledge/strategy-docs'
import { AuditReportsPage } from '@/pages/knowledge/audit-reports'

// Risk page (merged with monitoring)
import { RiskControlPage } from '@/pages/trading/risk-control'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AuthenticatedApp() {
  useWSStatus()
  return <AppShell />
}

function AuthInitializer({ children }: { children: React.ReactNode }) {
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      const token = useAuthStore.getState().token
      if (token) {
        useAuthStore.getState().checkAuth()
      }
      setHydrated(true)
    })

    if (useAuthStore.persist.hasHydrated()) {
      const token = useAuthStore.getState().token
      if (token) {
        useAuthStore.getState().checkAuth()
      }
      setHydrated(true)
    }

    return () => unsub()
  }, [])

  if (!hydrated) {
    return null
  }

  return <>{children}</>
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthInitializer>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AuthenticatedApp />
              </ProtectedRoute>
            }
          >
            {/* Default */}
            <Route index element={<Navigate to="/trading/overview" replace />} />

            {/* 策略研究 */}
            <Route path="research/factors" element={<FactorResearchPage />} />
            <Route path="research/strategies" element={<StrategyDevPage />} />
            <Route path="research/backtest" element={<BacktestCenterPage />} />
            <Route path="research/validation" element={<ValidationPage />} />
            <Route path="research/optimization" element={<OptimizationPage />} />

            {/* 策略交易 */}
            <Route path="trading/overview" element={<TradingOverviewPage />} />
            <Route path="trading/positions" element={<PositionsPage />} />
            <Route path="trading/orders" element={<OrdersPage />} />
            <Route path="trading/signals" element={<SignalsPage />} />
            <Route path="trading/risk" element={<RiskControlPage />} />
            <Route path="trading/instances" element={<StrategyInstancesPage />} />
            <Route path="trading/audit" element={<AuditPage />} />

            {/* 量化知识库 */}
            <Route path="knowledge/chat" element={<ChatPage />} />
            <Route path="knowledge/docs" element={<StrategyDocsPage />} />
            <Route path="knowledge/reports" element={<AuditReportsPage />} />

            {/* Legacy redirects */}
            <Route path="positions" element={<Navigate to="/trading/positions" replace />} />
            <Route path="orders" element={<Navigate to="/trading/orders" replace />} />
            <Route path="signals" element={<Navigate to="/trading/signals" replace />} />
            <Route path="risk" element={<Navigate to="/trading/risk" replace />} />
            <Route path="strategies" element={<Navigate to="/research/strategies" replace />} />
            <Route path="backtest" element={<Navigate to="/research/backtest" replace />} />
            <Route path="audit" element={<Navigate to="/trading/audit" replace />} />
            <Route path="monitoring" element={<Navigate to="/trading/risk" replace />} />
            <Route path="chat" element={<Navigate to="/knowledge/chat" replace />} />
          </Route>
        </Routes>
        <ToastContainer />
      </AuthInitializer>
    </ErrorBoundary>
  )
}
