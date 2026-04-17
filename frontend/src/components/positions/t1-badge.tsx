export function T1Badge({ isT1 }: { isT1: boolean }) {
  if (!isT1) return null
  return (
    <span className="ml-1.5 inline-flex items-center rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700">
      T+1
    </span>
  )
}
