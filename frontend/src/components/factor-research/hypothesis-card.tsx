interface HypothesisCardProps {
  content: string
}

/** Parse semi-structured hypothesis text into key-value pairs. */
function parseHypothesis(text: string): Record<string, string> {
  const fields: Record<string, string> = {}
  const lines = text.split('\n')
  for (const line of lines) {
    const match = line.match(/^[-•]\s*(.+?):\s*(.+)$/u)
    if (match) {
      fields[match[1].trim()] = match[2].trim()
    }
  }
  return fields
}

const FIELD_LABELS: Record<string, string> = {
  '假设描述': 'desc',
  '适用标的': 'scope',
  '时间范围': 'time_range',
  '触发条件': 'trigger',
  '目标变量': 'target',
  '显著性': 'significance',
  '稳定性': 'stability',
  '风险提示': 'risk',
}

export function HypothesisCard({ content }: HypothesisCardProps) {
  const fields = parseHypothesis(content)
  const hasStructured = Object.keys(fields).length > 0

  return (
    <div className="rounded border border-purple-200 bg-purple-50 px-3 py-2">
      <div className="mb-1 text-xs font-semibold text-purple-700">假设</div>
      {hasStructured ? (
        <div className="space-y-1">
          {Object.entries(FIELD_LABELS).map(([label, _]) => {
            const value = fields[label]
            if (!value) return null
            return (
              <div key={label} className="text-xs">
                <span className="font-medium text-purple-600">{label}:</span>{' '}
                <span className="text-purple-800">{value}</span>
              </div>
            )
          })}
          {/* Remaining fields not in FIELD_LABELS */}
          {Object.entries(fields)
            .filter(([k]) => !(k in FIELD_LABELS))
            .map(([key, val]) => (
              <div key={key} className="text-xs">
                <span className="font-medium text-purple-600">{key}:</span>{' '}
                <span className="text-purple-800">{val}</span>
              </div>
            ))}
        </div>
      ) : (
        <div className="whitespace-pre-wrap text-xs text-purple-800">{content}</div>
      )}
    </div>
  )
}
