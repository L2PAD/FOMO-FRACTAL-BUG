import { useOrders } from "../../../hooks/zap/useOrders";
import { formatTs, statusTone } from "./zapUtils";

export default function OrdersPanel() {
  const { data, error } = useOrders();

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <div className="mb-3">
        <div className="text-sm font-medium text-gray-900">Orders</div>
        <div className="text-xs text-gray-500">Submitted and open orders</div>
      </div>

      {error && <div className="text-sm text-red-600 mb-2">{error}</div>}

      <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
        {data.length === 0 ? (
          <div className="text-sm text-gray-500">No orders</div>
        ) : (
          data.map((order) => (
            <div
              key={order.order_id || order.exchange_order_id}
              className="border border-gray-100 rounded-lg p-3"
            >
              <div className="flex items-center justify-between">
                <div className="font-medium text-sm text-gray-900">
                  {order.symbol}
                </div>
                <div className={`text-xs font-semibold ${statusTone(order.status)}`}>
                  {order.status}
                </div>
              </div>

              <div className="mt-1 text-sm text-gray-700">
                {order.side} · {order.type}
              </div>

              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-500">
                <div>Qty: {order.quantity ?? order.qty ?? "—"}</div>
                <div>Filled: {order.filled_qty ?? "—"}</div>
                <div>Price: {order.price ?? order.avg_price ?? "MARKET"}</div>
                <div>Time: {formatTs(order.timestamp || order.created_at)}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
