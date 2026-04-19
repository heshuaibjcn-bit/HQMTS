import {
  LayoutDashboard,
  Briefcase,
  FileText,
  Activity,
  ShieldAlert,
  Cpu,
  ClipboardList,
  FlaskConical,
  LineChart,
  BookOpen,
  Search,
  Code,
  BarChart3,
  ShieldCheck,
  GitCompare,
  MessageSquare,
  FileCode2,
  ScrollText,
} from 'lucide-react'
import { SidebarSection } from './sidebar-section'

const researchItems = [
  { to: '/research/factors', label: '因子研究', icon: Search },
  { to: '/research/strategies', label: '策略开发', icon: Code },
  { to: '/research/backtest', label: '回测中心', icon: BarChart3 },
  { to: '/research/validation', label: '策略验证', icon: ShieldCheck },
  { to: '/research/optimization', label: '优化迭代', icon: GitCompare },
]

const tradingItems = [
  { to: '/trading/overview', label: '交易总览', icon: LayoutDashboard },
  { to: '/trading/positions', label: '持仓管理', icon: Briefcase },
  { to: '/trading/orders', label: '委托管理', icon: FileText },
  { to: '/trading/signals', label: '信号监控', icon: Activity },
  { to: '/trading/risk', label: '风控中心', icon: ShieldAlert },
  { to: '/trading/instances', label: '策略实例', icon: Cpu },
  { to: '/trading/audit', label: '审计追踪', icon: ClipboardList },
]

const knowledgeItems = [
  { to: '/knowledge/chat', label: 'AI 助手', icon: MessageSquare },
  { to: '/knowledge/docs', label: '策略文档', icon: FileCode2 },
  { to: '/knowledge/reports', label: '审计报告', icon: ScrollText },
]

export function Sidebar() {
  return (
    <aside className="flex w-56 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="flex h-14 items-center border-b border-[var(--color-border)] px-4">
        <FlaskConical className="mr-2 h-5 w-5 text-[var(--color-primary)]" />
        <span className="text-lg font-bold text-[var(--color-text)]">HQMTS</span>
      </div>
      <nav className="flex-1 overflow-auto px-2 py-2">
        <SidebarSection
          title="策略研究"
          icon={FlaskConical}
          sectionKey="research"
          items={researchItems}
        />
        <SidebarSection
          title="策略交易"
          icon={LineChart}
          sectionKey="trading"
          items={tradingItems}
        />
        <SidebarSection
          title="量化知识库"
          icon={BookOpen}
          sectionKey="knowledge"
          items={knowledgeItems}
        />
      </nav>
    </aside>
  )
}
