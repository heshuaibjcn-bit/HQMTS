import { useState, useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table'
import { useFactors, type FactorInfo } from '@/hooks/use-factor-research'
import { Search } from 'lucide-react'

const CATEGORY_LABELS: Record<string, string> = {
  trend: '趋势',
  momentum: '动量',
  volatility: '波动率',
  volume: '成交量',
  structure: '结构',
  time: '时间',
  market_state: '市场状态',
  cross_cycle: '跨周期',
}

const CATEGORY_COLORS: Record<string, string> = {
  trend: 'bg-blue-100 text-blue-700',
  momentum: 'bg-purple-100 text-purple-700',
  volatility: 'bg-orange-100 text-orange-700',
  volume: 'bg-green-100 text-green-700',
  structure: 'bg-cyan-100 text-cyan-700',
  time: 'bg-yellow-100 text-yellow-700',
  market_state: 'bg-pink-100 text-pink-700',
  cross_cycle: 'bg-indigo-100 text-indigo-700',
}

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS)

const columns: ColumnDef<FactorInfo>[] = [
  {
    accessorKey: 'name',
    header: '因子名称',
    cell: ({ getValue }) => (
      <span className="font-mono text-sm font-medium text-[var(--color-text)]">
        {getValue() as string}
      </span>
    ),
  },
  {
    accessorKey: 'category',
    header: '类别',
    cell: ({ getValue }) => {
      const cat = getValue() as string
      return (
        <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${CATEGORY_COLORS[cat] ?? 'bg-gray-100 text-gray-700'}`}>
          {CATEGORY_LABELS[cat] ?? cat}
        </span>
      )
    },
  },
  {
    accessorKey: 'version',
    header: '版本',
  },
  {
    accessorKey: 'description',
    header: '描述',
    cell: ({ getValue }) => (
      <span className="text-[var(--color-text-secondary)]">{getValue() as string}</span>
    ),
  },
  {
    accessorKey: 'params',
    header: '参数',
    cell: ({ getValue }) => {
      const params = getValue() as Record<string, unknown>
      const entries = Object.entries(params)
      if (entries.length === 0) return <span className="text-[var(--color-text-muted)]">--</span>
      return (
        <span className="font-mono text-xs text-[var(--color-text-muted)]">
          {entries.map(([k, v]) => `${k}=${v}`).join(', ')}
        </span>
      )
    },
  },
]

export function FactorLibraryTable() {
  const { data: factors, isLoading } = useFactors()
  const [search, setSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')

  const filtered = useMemo(() => {
    let list = factors ?? []
    if (selectedCategory) {
      list = list.filter((f) => f.category === selectedCategory)
    }
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (f) =>
          f.name.toLowerCase().includes(q) ||
          f.description.toLowerCase().includes(q),
      )
    }
    return list
  }, [factors, search, selectedCategory])

  const table = useReactTable({
    data: filtered,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            type="text"
            placeholder="搜索因子名称或描述..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] py-1.5 pl-8 pr-3 text-sm text-[var(--color-text)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-primary)]"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => setSelectedCategory('')}
            className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
              selectedCategory === ''
                ? 'bg-[var(--color-primary)] text-white'
                : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
            }`}
          >
            全部
          </button>
          {ALL_CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
              }`}
            >
              {CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载因子库...</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
          <table className="w-full text-sm">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-[var(--color-border)] bg-[var(--color-bg-tertiary)]">
                  {hg.headers.map((header) => (
                    <th key={header.id} className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="py-8 text-center text-[var(--color-text-muted)]">
                    没有匹配的因子
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="border-t border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3 py-1.5 text-xs text-[var(--color-text-muted)]">
            共 {filtered.length} 个因子
          </div>
        </div>
      )}
    </div>
  )
}
