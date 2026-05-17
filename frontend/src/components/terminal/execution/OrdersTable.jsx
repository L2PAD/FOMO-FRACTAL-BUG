export default function OrdersTable({ orders = [] }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4" data-testid="orders-table">
      <div className="text-white font-semibold mb-3">Orders</div>

      {!orders.length ? (
        <div className="text-gray-500 text-sm text-center py-6">No orders</div>
      ) : (
        <div className="space-y-2 max-h-[300px] overflow-y-auto custom-scrollbar">
          {orders.map((o, i) => (
            <div 
              key={i} 
              className="grid grid-cols-5 gap-3 text-sm border-b border-gray-800/50 pb-2 hover:bg-gray-800/30 px-2 py-1 rounded transition-colors"
              data-testid={`order-${i}`}
            >
              <div className="text-white font-medium">{o.symbol}</div>
              <div className={o.side === "BUY" ? "text-green-400" : "text-red-400"}>
                {o.side}
              </div>
              <div className="text-gray-300">{o.type}</div>
              <div className="text-gray-300">{o.status}</div>
              <div className="text-gray-400">{o.quantity || o.qty}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
