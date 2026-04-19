import { type LucideIcon, ChevronRight } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'
import { useSidebarStore, type SidebarSection } from '@/stores/sidebar-store'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

interface SidebarSectionProps {
  title: string
  icon: LucideIcon
  sectionKey: SidebarSection
  items: NavItem[]
}

export function SidebarSection({ title, icon: SectionIcon, sectionKey, items }: SidebarSectionProps) {
  const expanded = useSidebarStore((s) => s.expandedSections[sectionKey])
  const toggleSection = useSidebarStore((s) => s.toggleSection)
  const location = useLocation()

  const hasActive = items.some((item) => location.pathname === item.to || location.pathname.startsWith(item.to + '/'))

  const sectionId = `sidebar-section-${sectionKey}`

  return (
    <div className="mt-1">
      <button
        onClick={() => toggleSection(sectionKey)}
        aria-expanded={expanded}
        aria-controls={sectionId}
        className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
          hasActive
            ? 'text-[var(--color-primary)]'
            : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]'
        }`}
      >
        <SectionIcon className="h-3.5 w-3.5" />
        <span className="flex-1 text-left">{title}</span>
        <ChevronRight
          className={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
        />
      </button>
      <div
        id={sectionId}
        role="region"
        aria-label={title}
        className="grid transition-[grid-template-rows] duration-200 ease-in-out"
        style={{ gridTemplateRows: expanded ? '1fr' : '0fr' }}
      >
        <div className="overflow-hidden">
          <div className="space-y-0.5 pb-1">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-md px-3 py-1.5 text-sm transition-colors ${
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
          </div>
        </div>
      </div>
    </div>
  )
}
