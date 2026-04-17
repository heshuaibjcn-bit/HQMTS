import { useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { usePositions, type Position } from '@/hooks/use-positions'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { T1Badge } from './t1-badge'
import { PositionDetailDialog } from './position-detail-dialog'

const columns: ColumnDef<Position>[] = [
  {
    accessorKey: 'instrument_code',
    header: '代码',
    cell: ({ row }) => (
      <div>
        <span className="font-medium">{row.original.instrument_code}</span>
        <span className="ml-2 text-xs text-[var(--color-text-muted)]">
          {row.original.instrument_name}
        </span>
      </div>
    ),
  },
  {
    accessorKey: 'direction',
    header: '方向',
    cell: ({ getValue }) => {
      const dir = getValue() as string
      return (
        <span
          className={
            dir === 'long' ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'
          }
        >
          {dir === 'long' ? '多' : '空'}
        </span>
      )
    },
  },
  {
    accessorKey: 'quantity',
    header: '数量',
    cell: ({ row }) => (
      <div>
        {row.original.quantity}
        <span className="ml-1 text-xs text-[var(--color-text-muted)]">
          (可卖 {row.original.available_quantity})
        </span>
      </div>
    ),
  },
  {
    accessorKey: 'avg_cost',
    header: '成本价',
    cell: ({ getValue }) => formatCurrency(getValue() as number),
  },
  {
    accessorKey: 'market_value',
    header: '市值',
    cell: ({ getValue }) => formatCurrency(getValue() as number),
  },
  {
    accessorKey: 'unrealized_pnl',
    header: '浮盈',
    cell: ({ row }) => {
      const pnl = row.original.unrealized_pnl
      const pct = row.original.unrealized_pnl_pct
      return (
        <div>
          <div className={pnl >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'}>
            {formatCurrency(pnl)}
          </div>
          <div
            className={`text-xs ${pnl >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'}`}
          >
            {formatPercent(pct)}
          </div>
        </div>
      )
    },
  },
  {
    id: 't1',
    header: '',
    cell: ({ row }) => <T1Badge isT1={row.original.is_t1} />,
  },
]

export function PositionsTable() {
  const { data, isLoading } = usePositions()
  const [sorting, setSorting] = useState<SortingState>([])
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null)

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  })

  if (isLoading) {
    return <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载中...</div>
  }

  return (
    <>
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
                  暂无持仓
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="cursor-pointer border-b border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]"
                  onClick={() => setSelectedPosition(row.original)}
                >
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
      {selectedPosition && (
        <PositionDetailDialog
          position={selectedPosition}
          onClose={() => setSelectedPosition(null)}
        />
      )}
    </>
  )
}
