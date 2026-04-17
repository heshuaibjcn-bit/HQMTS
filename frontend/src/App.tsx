import { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth-store'
import { useWSStatus } from '@/hooks/use-websocket'
import { ToastContainer } from '@/components/ui/toast'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { LoginPage } from '@/pages/login'
import { AppShell } from '@/components/layout/app-shell'
import { OverviewPage } from '@/pages/overview'
import { PositionsPage } from '@/pages/positions'
import { OrdersPage } from '@/pages/orders'
import { RiskPage } from '@/pages/risk'
import { StrategiesPage } from '@/pages/strategies'
import { ChatPage } from '@/pages/chat'
import { SignalsPage } from '@/pages/signals'
import { BacktestPage } from '@/pages/backtest'
import { AuditPage } from '@/pages/audit'
import { MonitoringPage } from '@/pages/monitoring'

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
    // Wait for Zustand persist to hydrate from localStorage.
    // useAuthStore.persist.onFinishHydration fires once after rehydration.
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      const token = useAuthStore.getState().token
      if (token) {
        useAuthStore.getState().checkAuth()
      }
      setHydrated(true)
    })

    // Edge case: hydration may have already finished before we subscribed.
    // If so, hydrate immediately.
    if (useAuthStore.persist.hasHydrated()) {
      const token = useAuthStore.getState().token
      if (token) {
        useAuthStore.getState().checkAuth()
      }
      setHydrated(true)
    }

    return () => unsub()
  }, [])

  // Don't render routes until hydration completes to avoid login page flash
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
            <Route index element={<OverviewPage />} />
            <Route path="positions" element={<PositionsPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="risk" element={<RiskPage />} />
            <Route path="strategies" element={<StrategiesPage />} />
            <Route path="signals" element={<SignalsPage />} />
            <Route path="backtest" element={<BacktestPage />} />
            <Route path="audit" element={<AuditPage />} />
            <Route path="monitoring" element={<MonitoringPage />} />
            <Route path="chat" element={<ChatPage />} />
          </Route>
        </Routes>
        <ToastContainer />
      </AuthInitializer>
    </ErrorBoundary>
  )
}
