import React, { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const OrdersPanel = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchOrders = async () => {
    try {
      const res = await fetch(`${API_URL}/api/exchange/orders`);
      const data = await res.json();
      
      if (data.ok && data.orders) {
        setOrders(data.orders);
      }
    } catch (error) {
      console.error('Orders fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
    const interval = setInterval(fetchOrders, 3000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'FILLED': return 'bg-green-50 text-green-700';
      case 'NEW': return 'bg-blue-50 text-blue-700';
      case 'CANCELED': return 'bg-gray-50 text-gray-700';
      case 'REJECTED': return 'bg-red-50 text-red-700';
      default: return 'bg-gray-50 text-gray-700';
    }
  };

  return (
    <div className="bg-white rounded-xl p-4 border border-[#e6eaf2]" style={{ boxShadow: '2px 2px 8px rgba(0,5,48,0.06)' }}>
      <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">Orders ({orders.length})</h3>
      
      <div className="space-y-2 max-h-[200px] overflow-y-auto">
        {loading ? (
          <div className="text-center py-4 text-sm text-gray-400">Loading...</div>
        ) : orders.length === 0 ? (
          <div className="text-center py-4 text-sm text-gray-400">No orders</div>
        ) : (
          orders.map((order, idx) => (
            <div key={idx} className="pb-2 border-b border-gray-100 last:border-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{order.symbol?.replace('USDT', '') || order.symbol}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    order.side === 'BUY' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                  }`}>
                    {order.side}
                  </span>
                </div>
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${getStatusColor(order.status)}`}>
                  {order.status}
                </span>
              </div>
              <div className="flex items-center justify-between mt-0.5">
                <span className="text-xs text-gray-500">
                  Qty: {order.quantity?.toFixed(4) || '0'}
                </span>
                {order.avg_fill_price && (
                  <span className="text-xs text-gray-500">
                    Fill: ${order.avg_fill_price.toFixed(2)}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default OrdersPanel;
