import { useState, useCallback } from 'react'
import { FactorLibraryTable } from '@/components/factor-research/factor-library-table'
import { FactorComputationPanel } from '@/components/factor-research/factor-computation-panel'
import { ResearchChatPanel } from '@/components/factor-research/research-chat-panel'
import { GovernanceDashboard } from '@/components/factor-research/governance-dashboard'
import { ResearchReportViewer } from '@/components/factor-research/research-report-viewer'
import { ProjectList } from '@/components/factor-research/project-list'
import { ProjectCreationDialog } from '@/components/factor-research/project-creation-dialog'
import { ProjectWorkflow } from '@/components/factor-research/project-workflow'
import { CycleMonitor } from '@/components/factor-research/cycle-monitor'
import { CycleDetail } from '@/components/factor-research/cycle-detail'

type Tab = 'projects' | 'compute' | 'ai' | 'governance' | 'report' | 'cycles'

const TABS: { key: Tab; label: string }[] = [
  { key: 'projects', label: '研究项目' },
  { key: 'cycles', label: '研发循环' },
  { key: 'compute', label: '因子计算' },
  { key: 'ai', label: 'AI 研究' },
  { key: 'governance', label: '治理看板' },
  { key: 'report', label: '研究报告' },
]

export interface ResearchContext {
  instruments: string[]
  factors: string[]
  timeRange: string
}

export function FactorResearchPage() {
  const [activeTab, setActiveTab] = useState<Tab>('projects')
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [researchContext, setResearchContext] = useState<ResearchContext>({
    instruments: [],
    factors: [],
    timeRange: '',
  })

  const handleContextChange = useCallback((ctx: ResearchContext) => {
    setResearchContext(ctx)
  }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">因子研究</h1>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-md bg-[var(--color-bg-tertiary)] p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-[var(--color-bg)] text-[var(--color-text)] shadow-sm'
                : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'cycles' && (
        <>
          {selectedCycleId ? (
            <CycleDetail
              cycleId={selectedCycleId}
              onBack={() => setSelectedCycleId(null)}
            />
          ) : (
            <CycleMonitor onSelectCycle={setSelectedCycleId} />
          )}
        </>
      )}
      {activeTab === 'projects' && (
        <>
          {selectedProjectId ? (
            <ProjectWorkflow
              projectId={selectedProjectId}
              onBack={() => setSelectedProjectId(null)}
            />
          ) : (
            <ProjectList
              onSelectProject={setSelectedProjectId}
              onCreateClick={() => setShowCreateDialog(true)}
            />
          )}
        </>
      )}
      {activeTab === 'compute' && (
        <FactorComputationPanel onContextChange={handleContextChange} />
      )}
      {activeTab === 'ai' && <ResearchChatPanel context={researchContext} />}
      {activeTab === 'governance' && <GovernanceDashboard />}
      {activeTab === 'report' && <ResearchReportViewer />}

      <ProjectCreationDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onCreated={(id) => {
          setSelectedProjectId(id)
          setShowCreateDialog(false)
        }}
      />
    </div>
  )
}
