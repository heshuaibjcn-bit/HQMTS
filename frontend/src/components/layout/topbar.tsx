import { useAuthStore } from '@/stores/auth-store'
import { EnvironmentSwitcher } from './environment-switcher'
import { WsStatusBanner } from './ws-status-banner'
import { LogOut, User } from 'lucide-react'

export function Topbar() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  return (
    <div className="flex flex-col">
      <WsStatusBanner />
      <header className="flex h-14 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg)] px-4">
        <EnvironmentSwitcher />
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
            <User className="h-4 w-4" />
            <span>{user?.display_name || user?.username || '--'}</span>
          </div>
          <button
            onClick={logout}
            className="rounded-md p-1.5 text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]"
            title="退出登录"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>
    </div>
  )
}
