import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table'
import { useStrategies, type Strategy } from '@/hooks/use-strategies'
import { useCreateAdmission } from '@/hooks/use-validation'
import { useNotificationStore } from '@/stores/notification-store'
import { StrategyStatusBadge } from './strategy-status-badge'
import { ShieldCheck, AlertCircle, RefreshCw } from 'lucide-react'

const ELIGIBLE_STATUSES = ['backtested', 'validated', 'ready']

export function StrategiesTable() {
  const { data, isLoading, isError, refetch } = useStrategies()
  const createAdmission = useCreateAdmission()
  const toast = useNotificationStore.getState().addNotification

  const handleSubmitForValidation = async (strategy: Strategy) => {
    try {
      await createAdmission.mutateAsync({
        strategy_instance_id: strategy.strategy_id,
        strategy_version: undefined,
      })
      toast('success', `策略 ${strategy.name} 已提交验证`)
    } catch (err) {
      console.error('提交验证失败:', err)
      toast('error', '提交验证失败，请稍后重试')
    }
  }

  const columns: ColumnDef<Strategy>[] = [
    {
      accessorKey: 'name',
      header: '策略名称',
    },
    {
      accessorKey: 'type',
      header: '类型',
    },
    {
      accessorKey: 'status',
      header: '状态',
      cell: ({ getValue }) => <StrategyStatusBadge status={getValue() as string} />,
    },
    {
      accessorKey: 'created_at',
      header: '创建时间',
      cell: ({ getValue }) => new Date(getValue() as string).toLocaleDateString('zh-CN'),
    },
    {
      id: 'actions',
      header: '操作',
      cell: ({ row }) => {
        const eligible = ELIGIBLE_STATUSES.includes(row.original.status)
        return (
          <button
            onClick={() => handleSubmitForValidation(row.original)}
            disabled={!eligible || createAdmission.isPending}
            title={eligible ? '提交准入验证' : '策略状态不符合验证条件'}
            className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ShieldCheck className="h-3 w-3" />
            提交验证
          </button>
        )
      },
    },
  ]

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
        <p className="text-sm text-[var(--color-danger)]">加载策略失败</p>
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
                暂无策略
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
