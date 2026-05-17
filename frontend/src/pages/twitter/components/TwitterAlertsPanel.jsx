/**
 * Twitter Alerts Panel
 * 
 * Bell icon + dropdown with real-time alerts from backend.
 * Fetches from /api/connections/overview/alerts
 * Supports mark-as-read and auto-evaluate.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Bell, AlertTriangle, Zap, TrendingUp, Info, Check, X } from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const SEVERITY_CONFIG = {
  critical: { bg: 'bg-red-50', border: 'border-red-200', icon: AlertTriangle, iconColor: 'text-red-500', dot: 'bg-red-500' },
  high: { bg: 'bg-orange-50', border: 'border-orange-200', icon: Zap, iconColor: 'text-orange-500', dot: 'bg-orange-500' },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', icon: TrendingUp, iconColor: 'text-amber-500', dot: 'bg-amber-500' },
  info: { bg: 'bg-blue-50', border: 'border-blue-200', icon: Info, iconColor: 'text-blue-500', dot: 'bg-blue-500' },
  low: { bg: 'bg-gray-50', border: 'border-gray-200', icon: Info, iconColor: 'text-gray-500', dot: 'bg-gray-400' },
};

export default function TwitterAlertsPanel() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const ref = useRef(null);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/connections/overview/alerts?limit=20`);
      const data = await res.json();
      if (data.ok) {
        setAlerts(data.alerts || []);
        setUnreadCount(data.unreadCount || 0);
      }
    } catch {}
  }, []);

  // Evaluate + fetch on mount
  useEffect(() => {
    const init = async () => {
      try {
        await fetch(`${API_BASE}/api/connections/overview/alerts/evaluate`, { method: 'POST' });
      } catch {}
      fetchAlerts();
    };
    init();
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/connections/overview/alerts/evaluate`, { method: 'POST' }).catch(() => {});
      fetchAlerts();
    }, 120000); // 2 min
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const markAllRead = async () => {
    try {
      await fetch(`${API_BASE}/api/connections/overview/alerts/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      setAlerts(prev => prev.map(a => ({ ...a, read: true })));
      setUnreadCount(0);
    } catch {}
  };

  const timeAgo = (dateStr) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <div ref={ref} className="relative">
      {/* Bell Button */}
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
        data-testid="alerts-bell-btn"
      >
        <Bell className={`w-5 h-5 ${unreadCount > 0 ? 'text-blue-600' : 'text-gray-500'}`} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4.5 h-4.5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center min-w-[18px] h-[18px]" data-testid="alerts-badge">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-[380px] bg-white border border-gray-200 rounded-2xl shadow-xl z-50 overflow-hidden" data-testid="alerts-panel">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <Bell className="w-4 h-4 text-gray-700" />
              <span className="text-sm font-semibold text-gray-800">Alerts</span>
              {unreadCount > 0 && (
                <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-medium">
                  {unreadCount} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  className="text-[10px] text-blue-500 hover:text-blue-600 font-medium px-2 py-1 rounded-md hover:bg-blue-50 transition-colors"
                  data-testid="mark-all-read-btn"
                >
                  <Check className="w-3 h-3 inline mr-0.5" />
                  Mark all read
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1 hover:bg-gray-100 rounded-md transition-colors"
              >
                <X className="w-3.5 h-3.5 text-gray-400" />
              </button>
            </div>
          </div>

          {/* Alerts list */}
          <div className="max-h-[400px] overflow-y-auto">
            {alerts.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <Bell className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-400">No alerts yet</p>
                <p className="text-xs text-gray-300 mt-1">Alerts trigger when CAS &gt; 75 or pump patterns detected</p>
              </div>
            ) : (
              alerts.map(alert => {
                const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low;
                const Icon = config.icon;
                return (
                  <div
                    key={alert.id}
                    className={`px-4 py-3 border-b border-gray-50 transition-colors ${!alert.read ? config.bg : 'bg-white hover:bg-gray-50'}`}
                    data-testid={`alert-item-${alert.id}`}
                  >
                    <div className="flex gap-3">
                      <div className={`w-8 h-8 rounded-lg ${!alert.read ? config.bg : 'bg-gray-100'} ${!alert.read ? config.border : 'border-gray-200'} border flex items-center justify-center flex-shrink-0`}>
                        <Icon className={`w-4 h-4 ${!alert.read ? config.iconColor : 'text-gray-400'}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className={`text-xs font-semibold ${!alert.read ? 'text-gray-900' : 'text-gray-600'}`}>
                            {alert.title}
                          </span>
                          {!alert.read && <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />}
                        </div>
                        <p className="text-[11px] text-gray-500 leading-relaxed">{alert.message}</p>
                        {alert.data?.tokens && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {alert.data.tokens.slice(0, 4).map(t => (
                              <span key={t} className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-medium">{t}</span>
                            ))}
                          </div>
                        )}
                        <span className="text-[10px] text-gray-400 mt-1 block">{timeAgo(alert.createdAt)}</span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
