import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type SidebarSection = 'research' | 'trading' | 'knowledge'

const sectionDefaults: Record<SidebarSection, boolean> = {
  research: true,
  trading: true,
  knowledge: false,
}

interface SidebarState {
  expandedSections: Record<SidebarSection, boolean>
  toggleSection: (section: SidebarSection) => void
  expandSection: (section: SidebarSection) => void
  collapseOthers: (section: SidebarSection) => void
}

export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      expandedSections: { ...sectionDefaults },
      toggleSection: (section) =>
        set((state) => ({
          expandedSections: {
            ...state.expandedSections,
            [section]: !state.expandedSections[section],
          },
        })),
      expandSection: (section) =>
        set((state) => ({
          expandedSections: {
            ...state.expandedSections,
            [section]: true,
          },
        })),
      collapseOthers: (section) =>
        set(() => ({
          expandedSections: {
            research: section === 'research',
            trading: section === 'trading',
            knowledge: section === 'knowledge',
          },
        })),
    }),
    { name: 'hqmts-sidebar' },
  ),
)
