interface TrialResultCardProps {
  content: string
}

/** Parse semi-structured trial result text. */
function parseTrialResult(text: string): Record<string, string> {
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

export function TrialResultCard({ content }: TrialResultCardProps) {
  const fields = parseTrialResult(content)
  const hasStructured = Object.keys(fields).length > 0

  return (
    <div className="rounded border border-green-200 bg-green-50 px-3 py-2">
      <div className="mb-1 text-xs font-semibold text-green-700">试验结果</div>
      {hasStructured ? (
        <div className="space-y-1">
          {Object.entries(fields).map(([key, val]) => (
            <div key={key} className="text-xs">
              <span className="font-medium text-green-600">{key}:</span>{' '}
              <span className="text-green-800">{val}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="whitespace-pre-wrap text-xs text-green-800">{content}</div>
      )}
    </div>
  )
}
