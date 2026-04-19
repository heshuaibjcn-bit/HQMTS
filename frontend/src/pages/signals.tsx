import { useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { useSignals, type Signal } from '@/hooks/use-signals'
import { formatTime } from '@/lib/utils'

const columns: ColumnDef<Signal>[] = [
  {
    accessorKey: 'strategy_name',
    header: '策略',
  },
  {
    accessorKey: 'instrument_code',
    header: '标的',
  },
  {
    accessorKey: 'direction',
    header: '方向',
    cell: ({ getValue }) => {
      const dir = getValue() as string
      const map: Record<string, { label: string; color: string }> = {
        open_long: { label: '开多', color: 'text-[var(--color-danger)]' },
        close_long: { label: '平多', color: 'text-[var(--color-success)]' },
        open_short: { label: '开空', color: 'text-[var(--color-success)]' },
        close_short: { label: '平空', color: 'text-[var(--color-danger)]' },
        flatten: { label: '平仓', color: 'text-amber-600' },
        hold: { label: '持有', color: 'text-[var(--color-text-muted)]' },
      }
      const info = map[dir] ?? { label: dir, color: 'text-[var(--color-text)]' }
      return <span className={info.color}>{info.label}</span>
    },
  },
  {
    accessorKey: 'strength',
    header: '强度',
    cell: ({ getValue }) => {
      const s = getValue() as number
      const pct = Math.round(s * 100)
      return (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-16 rounded-full bg-[var(--color-bg-tertiary)]">
            <div
              className="h-1.5 rounded-full bg-[var(--color-primary)]"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-xs text-[var(--color-text-muted)]">{pct}%</span>
        </div>
      )
    },
  },
  {
    accessorKey: 'price_target',
    header: '目标价',
    cell: ({ getValue }) => {
      const v = getValue() as number | null
      return v != null ? v.toFixed(2) : '--'
    },
  },
  {
    accessorKey: 'created_at',
    header: '时间',
    cell: ({ getValue }) => formatTime(getValue() as string),
  },
]

export function SignalsPage() {
  const { data, isLoading } = useSignals()
  const [sorting, setSorting] = useState<SortingState>([])

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">信号监控</h1>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        {isLoading ? (
          <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载中...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id} className="border-b border-[var(--color-border)]">
                    {hg.headers.map((header) => (
                      <th
                        key={header.id}
                        className="cursor-pointer px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {{ asc: ' ↑', desc: ' ↓' }[header.column.getIsSorted() as string] ?? ''}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.length === 0 ? (
                  <tr>
                    <td colSpan={columns.length} className="py-8 text-center text-[var(--color-text-muted)]">
                      暂无信号
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
        )}
      </div>
    </div>
  )
}
