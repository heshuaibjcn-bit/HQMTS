import { OrdersTable } from '@/components/orders/orders-table'

export function OrdersPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">订单</h1>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <OrdersTable />
      </div>
    </div>
  )
}
