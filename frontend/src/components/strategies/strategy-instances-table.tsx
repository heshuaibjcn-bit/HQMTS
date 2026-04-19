import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table'
import { useStrategyInstances, type StrategyInstance } from '@/hooks/use-strategies'
import { StrategyStatusBadge } from './strategy-status-badge'
import { formatCurrency } from '@/lib/utils'
import { AlertCircle, RefreshCw } from 'lucide-react'

const columns: ColumnDef<StrategyInstance>[] = [
  {
    accessorKey: 'strategy_name',
    header: '策略',
  },
  {
    accessorKey: 'instrument_codes',
    header: '标的',
    cell: ({ getValue }) => (getValue() as string[] | undefined)?.join(', ') ?? '--',
  },
  {
    accessorKey: 'status',
    header: '状态',
    cell: ({ getValue }) => <StrategyStatusBadge status={getValue() as string} />,
  },
  {
    accessorKey: 'pnl',
    header: '盈亏',
    cell: ({ getValue }) => {
      const pnl = getValue() as number
      return (
        <span className={pnl >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'}>
          {formatCurrency(pnl)}
        </span>
      )
    },
  },
  {
    accessorKey: 'started_at',
    header: '启动时间',
    cell: ({ getValue }) => getValue() ? new Date(getValue() as string).toLocaleDateString('zh-CN') : '--',
  },
]

export function StrategyInstancesTable() {
  const { data, isLoading, isError, refetch } = useStrategyInstances()

  const table = useReactTable({
    data: data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  if (isLoading) {
    return <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载中...</div>
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-8">
        <AlertCircle className="h-8 w-8 text-[var(--color-danger)]" />
        <p className="text-sm text-[var(--color-danger)]">加载策略实例失败</p>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
        >
          <RefreshCw className="h-3 w-3" />
          重试
        </button>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="border-b border-[var(--color-border)]">
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
                暂无实例
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
    </div>
  )
}
