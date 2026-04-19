import { useGenerateReport, type ResearchReport } from '@/hooks/use-factor-research'
import { useState } from 'react'
import { useFactors } from '@/hooks/use-factor-research'
import { FileText, Loader2 } from 'lucide-react'

function ReportDisplay({ report }: { report: ResearchReport }) {
  return (
    <div className="space-y-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 text-[var(--color-primary)]" />
        <h3 className="text-sm font-semibold text-[var(--color-text)]">{report.title}</h3>
        <span className="text-xs text-[var(--color-text-muted)]">
          {new Date(report.created_at).toLocaleString('zh-CN')}
        </span>
      </div>

      <div className="text-xs text-[var(--color-text-muted)]">
        因子: {report.factor_names.join(', ')} | 标的: {report.instrument_ids.join(', ')} | 范围: {report.time_range_days} 天
      </div>

      {report.sections.map((section, idx) => (
        <div key={idx} className="rounded border border-[var(--color-border)] p-3">
          <h4 className="mb-2 text-xs font-semibold text-[var(--color-text)]">{section.title}</h4>

          {section.type === 'factor_analysis' && section.factors && (
            <div className="space-y-2">
              {section.factors.map((f) => (
                <div key={f.name} className="flex items-start gap-2 text-xs">
                  <span className="shrink-0 rounded bg-[var(--color-bg-tertiary)] px-1.5 py-0.5 font-mono font-medium text-[var(--color-text)]">
                    {f.name}
                  </span>
                  <span className="text-[var(--color-text-secondary)]">{f.description}</span>
                </div>
              ))}
            </div>
          )}

          {section.type === 'governance' && section.stats && (
            <div className="grid grid-cols-2 gap-2 text-xs lg:grid-cols-4">
              <div>
                <span className="text-[var(--color-text-muted)]">总试验数:</span>{' '}
                <span className="font-medium text-[var(--color-text)]">{section.stats.total_trials}</span>
              </div>
              <div>
                <span className="text-[var(--color-text-muted)]">显著数:</span>{' '}
                <span className="font-medium text-[var(--color-text)]">{section.stats.significant_count}</span>
              </div>
              <div>
                <span className="text-[var(--color-text-muted)]">FWER:</span>{' '}
                <span className="font-medium text-[var(--color-text)]">{(section.stats.family_wise_error_rate * 100).toFixed(1)}%</span>
              </div>
              <div>
                <span className="text-[var(--color-text-muted)]">FDR:</span>{' '}
                <span className="font-medium text-[var(--color-text)]">{(section.stats.false_discovery_rate * 100).toFixed(1)}%</span>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export function ResearchReportViewer() {
  const { data: factors } = useFactors()
  const [title, setTitle] = useState('因子研究报告')
  const [selectedFactors, setSelectedFactors] = useState<string[]>([])
  const [instrumentIds, setInstrumentIds] = useState('')
  const generateMutation = useGenerateReport()

  const toggleFactor = (name: string) => {
    setSelectedFactors((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    )
  }

  const handleGenerate = () => {
    const ids = instrumentIds.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean)
    if (selectedFactors.length === 0 || ids.length === 0) return
    generateMutation.mutate({
      title,
      factor_names: selectedFactors,
      instrument_ids: ids,
      time_range_days: 250,
      include_governance: true,
    })
  }

  return (
    <div className="space-y-4">
      {/* Generation form */}
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4 space-y-3">
        <h3 className="text-sm font-medium text-[var(--color-text)]">生成研究报告</h3>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">报告标题</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">标的代码 (逗号分隔)</label>
            <input
              type="text"
              placeholder="如: 000001.SZ, 600519.SH"
              value={instrumentIds}
              onChange={(e) => setInstrumentIds(e.target.value)}
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">选择因子</label>
          <div className="flex flex-wrap gap-1">
            {(factors ?? []).map((f) => (
              <button
                key={f.name}
                onClick={() => toggleFactor(f.name)}
                className={`rounded px-2 py-0.5 text-xs font-mono transition-colors ${
                  selectedFactors.includes(f.name)
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                }`}
              >
                {f.name}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generateMutation.isPending || selectedFactors.length === 0 || !instrumentIds.trim()}
          className="flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50"
        >
          {generateMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          生成报告
        </button>
      </div>

      {/* Generated report */}
      {generateMutation.data && <ReportDisplay report={generateMutation.data} />}
      {generateMutation.isError && (
        <div className="rounded bg-red-50 px-3 py-2 text-xs text-red-600">
          生成失败: {generateMutation.error?.message}
        </div>
      )}
    </div>
  )
}
