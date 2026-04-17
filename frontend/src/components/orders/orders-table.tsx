import { useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { useOrders, type Order } from '@/hooks/use-orders'
import { formatCurrency, formatTime } from '@/lib/utils'
import { OrderStatusBadge } from './order-status-badge'
import { OrderDetailDialog } from './order-detail-dialog'
import { CancelOrderDialog } from './cancel-order-dialog'

const columns: ColumnDef<Order>[] = [
  {
    accessorKey: 'instrument_code',
    header: '标的',
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
        <span className={dir === 'buy' ? 'text-[var(--color-danger)]' : 'text-[var(--color-success)]'}>
          {dir === 'buy' ? '买入' : '卖出'}
        </span>
      )
    },
  },
  {
    accessorKey: 'price',
    header: '价格',
    cell: ({ getValue }) => formatCurrency(getValue() as number),
  },
  {
    accessorKey: 'quantity',
    header: '数量',
    cell: ({ row }) => (
      <span>
        {row.original.filled_quantity}/{row.original.quantity}
      </span>
    ),
  },
  {
    accessorKey: 'status',
    header: '状态',
    cell: ({ getValue }) => <OrderStatusBadge status={getValue() as string} />,
  },
  {
    accessorKey: 'created_at',
    header: '时间',
    cell: ({ getValue }) => formatTime(getValue() as string),
  },
]

export function OrdersTable() {
  const { data, isLoading } = useOrders()
  const [sorting, setSorting] = useState<SortingState>([])
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  const [cancelOrder, setCancelOrder] = useState<Order | null>(null)

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
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
                  暂无订单
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="cursor-pointer px-3 py-2"
                      onClick={() => setSelectedOrder(row.original)}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                  <td className="px-3 py-2">
                    {['pending', 'submitted', 'partial'].includes(row.original.status) && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setCancelOrder(row.original)
                        }}
                        className="text-xs text-[var(--color-danger)] hover:underline"
                      >
                        撤单
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {selectedOrder && (
        <OrderDetailDialog order={selectedOrder} onClose={() => setSelectedOrder(null)} />
      )}
      {cancelOrder && (
        <CancelOrderDialog order={cancelOrder} onClose={() => setCancelOrder(null)} />
      )}
    </>
  )
}
