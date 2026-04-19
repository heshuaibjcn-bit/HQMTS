import { useState } from 'react'
import { useCreateProject } from '@/hooks/use-factor-research'

interface ProjectCreationDialogProps {
  open: boolean
  onClose: () => void
  onCreated?: (projectId: string) => void
}

export function ProjectCreationDialog({ open, onClose, onCreated }: ProjectCreationDialogProps) {
  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const [instruments, setInstruments] = useState('')
  const [categories, setCategories] = useState('')
  const [mode, setMode] = useState('collaborative')
  const [budget, setBudget] = useState(100)

  const createProject = useCreateProject()

  if (!open) return null

  const handleSubmit = async () => {
    if (!title.trim() || !question.trim()) return

    const result = await createProject.mutateAsync({
      title: title.trim(),
      research_question: question.trim(),
      instrument_ids: instruments ? instruments.split(',').map((s) => s.trim()).filter(Boolean) : [],
      factor_categories: categories ? categories.split(',').map((s) => s.trim()).filter(Boolean) : [],
      trial_budget: budget,
      mode,
    })

    setTitle('')
    setQuestion('')
    setInstruments('')
    setCategories('')
    setMode('collaborative')
    setBudget(100)
    onCreated?.(result.research_project_id)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-lg bg-[var(--color-bg)] p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-[var(--color-text)]">新建研究项目</h2>

        <div className="mt-4 space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
              项目标题 *
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="如：银行股动量因子研究"
              className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-tertiary)]"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
              研究问题 *
            </label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="如：银行股的短期动量因子是否存在显著alpha？"
              rows={3}
              className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-tertiary)]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                标的（逗号分隔）
              </label>
              <input
                value={instruments}
                onChange={(e) => setInstruments(e.target.value)}
                placeholder="601398, 600036"
                className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text)]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                因子类别（逗号分隔）
              </label>
              <input
                value={categories}
                onChange={(e) => setCategories(e.target.value)}
                placeholder="trend, momentum"
                className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text)]"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                研究模式
              </label>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text)]"
              >
                <option value="collaborative">协作模式</option>
                <option value="ai_autonomous">AI自主</option>
                <option value="human_driven">人工驱动</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                试验预算
              </label>
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                min={1}
                max={1000}
                className="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text)]"
              />
            </div>
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={!title.trim() || !question.trim() || createProject.isPending}
            className="rounded bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {createProject.isPending ? '创建中...' : '创建项目'}
          </button>
        </div>
      </div>
    </div>
  )
}
