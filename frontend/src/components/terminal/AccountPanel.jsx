import React, { useState, useEffect } from 'react';
import { Database, Activity } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const AccountPanel = () => {
  const [account, setAccount] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [accountRes, statusRes] = await Promise.all([
        fetch(`${API_URL}/api/exchange/account`),
        fetch(`${API_URL}/api/exchange/status`)
      ]);

      const accountData = await accountRes.json();
      const statusData = await statusRes.json();

      if (accountData.ok && accountData.account) setAccount(accountData.account);
      if (statusData.ok) setStatus(statusData);
    } catch (error) {
      console.error('Account fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  const testOrder = async () => {
    try {
      const res = await fetch(`${API_URL}/api/exchange/test-order`, { method: 'POST' });
      const data = await res.json();
      
      if (data.ok) {
        alert(`Test order filled: ${data.test_order.symbol} ${data.test_order.side} @ $${data.test_order.avg_fill_price}`);
        fetchData(); // Refresh
      }
    } catch (error) {
      console.error('Test order failed:', error);
      alert('Test order failed');
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-xl p-4 border border-[#e6eaf2]" style={{ boxShadow: '2px 2px 8px rgba(0,5,48,0.06)' }}>
        <div className="text-sm text-gray-500">Loading account...</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl p-4 border border-[#e6eaf2]" style={{ boxShadow: '2px 2px 8px rgba(0,5,48,0.06)' }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Account</h3>
        <Database className="w-4 h-4 text-[#04A584]" />
      </div>
      
      <div className="space-y-2.5">
        {/* Exchange & Status */}
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500">Exchange</span>
          <span className="text-sm font-medium text-gray-900">{account?.exchange || 'N/A'}</span>
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500">Mode</span>
          <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-medium">
            {status?.mode || 'UNKNOWN'}
          </span>
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500">Status</span>
          <div className="flex items-center gap-1.5">
            <Activity className={`w-3 h-3 ${status?.connected ? 'text-green-500' : 'text-red-500'}`} />
            <span className={`text-xs font-medium ${status?.connected ? 'text-green-700' : 'text-red-700'}`}>
              {status?.connected ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>
        </div>

        {/* Equity */}
        {account && (
          <>
            <div className="border-t border-gray-100 pt-2.5 mt-2.5">
              <span className="text-xs text-gray-500 block mb-1">Equity</span>
              <span className="text-xl font-bold text-gray-900">
                ${(account.total_equity || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </span>
            </div>
            
            {/* Balance */}
            {account.balances && account.balances.length > 0 && (
              <div className="flex justify-between items-baseline">
                <span className="text-xs text-gray-500">Balance (USDT)</span>
                <span className="text-sm font-semibold text-gray-900">
                  ${account.balances[0].total.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                </span>
              </div>
            )}
          </>
        )}

        {/* Test Order Button */}
        <button
          onClick={testOrder}
          className="w-full mt-3 bg-[#04A584] hover:bg-[#03916e] text-white text-xs font-medium py-2 px-3 rounded transition-colors"
          data-testid="test-order-btn"
        >
          TEST ORDER
        </button>
      </div>
    </div>
  );
};

export default AccountPanel;
