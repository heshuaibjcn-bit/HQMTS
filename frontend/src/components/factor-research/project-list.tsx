import { useResearchProjects } from '@/hooks/use-factor-research'

const STAGE_LABELS: Record<string, string> = {
  exploration: '探索',
  hypothesis: '假设',
  design: '设计',
  execution: '执行',
  validation: '验证',
  report: '报告',
  completed: '已完成',
  failed: '失败',
  canceled: '已取消',
}

const STAGES = ['exploration', 'hypothesis', 'design', 'execution', 'validation', 'report']

const MODE_LABELS: Record<string, string> = {
  collaborative: '协作',
  ai_autonomous: 'AI自主',
  human_driven: '人工',
}

interface ProjectListProps {
  onSelectProject?: (projectId: string) => void
  onCreateClick?: () => void
}

export function ProjectList({ onSelectProject, onCreateClick }: ProjectListProps) {
  const { data, isLoading } = useResearchProjects()

  if (isLoading) {
    return <div className="py-8 text-center text-sm text-[var(--color-text-secondary)]">加载中...</div>
  }

  const projects = data?.projects ?? []

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-[var(--color-text-secondary)]">
          共 {data?.total ?? 0} 个项目
        </span>
        <button
          onClick={onCreateClick}
          className="rounded bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
        >
          新建项目
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="py-12 text-center text-sm text-[var(--color-text-secondary)]">
          暂无研究项目。点击「新建项目」开始因子研发。
        </div>
      ) : (
        <div className="grid gap-3">
          {projects.map((project) => {
            const stageIdx = STAGES.indexOf(project.current_stage)
            const isTerminal = ['completed', 'failed', 'canceled'].includes(project.status)

            return (
              <div
                key={project.research_project_id}
                onClick={() => onSelectProject?.(project.research_project_id)}
                className="cursor-pointer rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4 transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-medium text-[var(--color-text)]">
                      {project.title}
                    </h3>
                    <p className="mt-0.5 truncate text-xs text-[var(--color-text-secondary)]">
                      {project.research_question}
                    </p>
                  </div>
                  <span className="ml-2 shrink-0 rounded-full bg-[var(--color-bg-tertiary)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]">
                    {MODE_LABELS[project.mode] ?? project.mode}
                  </span>
                </div>

                {/* Stage progress bar */}
                {!isTerminal ? (
                  <div className="mt-3 flex items-center gap-1">
                    {STAGES.map((stage, i) => (
                      <div
                        key={stage}
                        className="h-1.5 flex-1 rounded-full transition-colors"
                        style={{
                          backgroundColor:
                            i <= stageIdx
                              ? 'var(--color-primary)'
                              : 'var(--color-bg-tertiary)',
                        }}
                      />
                    ))}
                    <span className="ml-2 text-[10px] text-[var(--color-text-secondary)]">
                      {STAGE_LABELS[project.current_stage] ?? project.current_stage}
                    </span>
                  </div>
                ) : (
                  <div className="mt-2 text-xs text-[var(--color-text-secondary)]">
                    {STAGE_LABELS[project.status] ?? project.status}
                  </div>
                )}

                <div className="mt-2 flex items-center gap-3 text-[10px] text-[var(--color-text-secondary)]">
                  <span>假设: {project.hypothesis_ids?.length ?? 0}</span>
                  <span>试验: {project.trial_ids?.length ?? 0}</span>
                  <span>预算: {project.trial_budget}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
