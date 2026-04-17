import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Briefcase,
  FileText,
  ShieldCheck,
  Cpu,
  Activity,
  BarChart3,
  ClipboardList,
  Monitor,
  MessageSquare,
} from 'lucide-react'

const navItems = [
  { to: '/', label: '总览', icon: LayoutDashboard },
  { to: '/positions', label: '持仓', icon: Briefcase },
  { to: '/orders', label: '订单', icon: FileText },
  { to: '/signals', label: '信号', icon: Activity },
  { to: '/risk', label: '风控', icon: ShieldCheck },
  { to: '/strategies', label: '策略', icon: Cpu },
  { to: '/backtest', label: '回测', icon: BarChart3 },
  { to: '/audit', label: '审计', icon: ClipboardList },
  { to: '/monitoring', label: '监控', icon: Monitor },
  { to: '/chat', label: 'AI 助手', icon: MessageSquare },
]

export function Sidebar() {
  return (
    <aside className="flex w-56 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="flex h-14 items-center border-b border-[var(--color-border)] px-4">
        <span className="text-lg font-bold text-[var(--color-text)]">HQMTS</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-auto p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]'
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
