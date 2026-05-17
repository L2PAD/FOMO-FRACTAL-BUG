/**
 * NotificationBell — Unified Notification Engine UI
 *
 * Reads from /api/notifications/feed (unified)
 * Shows unread count badge + dropdown with recent notifications
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { Bell, Check, Loader2, AlertTriangle, TrendingDown, Activity, Zap, Globe, Server } from 'lucide-react';
import { Link } from 'react-router-dom';
import * as notificationsApi from '../api/notifications.api';

const SOURCE_ICONS = {
  exchange: TrendingDown,
  onchain: Globe,
  sentiment: Activity,
  fractal: Zap,
  telegram: Zap,
  system: Server,
};

const PRIORITY_COLORS = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-blue-500',
  low: 'bg-gray-400',
};

export default function NotificationBell({ variant = 'default', collapsed = false }) {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);

  const loadFeed = useCallback(async () => {
    setLoading(true);
    try {
      const data = await notificationsApi.getFeed('user', 10);
      if (data?.ok) {
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread || 0);
      }
    } catch (err) {
      // Silent fail — bell still shows cached state
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + periodic refresh
  useEffect(() => {
    loadFeed();
    const interval = setInterval(loadFeed, 30000);
    return () => clearInterval(interval);
  }, [loadFeed]);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleMarkRead = async (id, e) => {
    e.stopPropagation();
    try {
      await notificationsApi.markAsRead(id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, readAt: new Date().toISOString() } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Mark read failed:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead('user');
      setNotifications(prev => prev.map(n => ({ ...n, readAt: new Date().toISOString() })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Mark all read failed:', err);
    }
  };

  const timeAgo = (dateStr) => {
    if (!dateStr) return '';
    const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const isSidebar = variant === 'sidebar';

  return (
    <div className={`relative ${isSidebar ? 'w-full' : ''}`} ref={dropdownRef}>
      <button
        onClick={() => { setIsOpen(!isOpen); if (!isOpen) loadFeed(); }}
        className={`relative ${
          isSidebar
            ? `flex items-center w-full ${collapsed ? 'justify-center' : 'gap-2.5'}`
            : 'p-2.5 hover:bg-gray-100 rounded-full'
        } transition-colors`}
        data-testid="notification-bell"
      >
        <Bell className={`flex-shrink-0 ${isSidebar ? 'w-[18px] h-[18px] text-current' : 'w-5 h-5 text-gray-600'}`} />
        {!collapsed && isSidebar && <span className="text-sm">Alerts</span>}
        {unreadCount > 0 && (
          <span
            className={`${
              isSidebar && !collapsed
                ? 'ml-auto min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1'
                : 'absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1'
            }`}
            data-testid="notification-bell-badge"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          className={`${
            isSidebar
              ? 'fixed left-16 top-auto z-[100] w-96'
              : 'absolute right-0 top-full mt-2 w-96 z-50'
          } bg-white border border-gray-200 rounded-xl shadow-2xl overflow-hidden`}
          style={isSidebar ? { transform: 'translateY(-50%)' } : undefined}
          data-testid="notification-dropdown"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50/50">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-gray-900 text-sm">Notifications</h3>
              {unreadCount > 0 && (
                <span className="text-[10px] bg-red-100 text-red-600 font-bold px-1.5 py-0.5 rounded-full">
                  {unreadCount} new
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                data-testid="mark-all-read-btn"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* Notifications List */}
          <div className="max-h-[400px] overflow-y-auto divide-y divide-gray-50">
            {loading && notifications.length === 0 ? (
              <div className="p-6 text-center">
                <Loader2 className="w-5 h-5 animate-spin text-gray-400 mx-auto" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-8 text-center">
                <Bell className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No notifications yet</p>
                <p className="text-xs text-gray-400 mt-1">Events will appear here</p>
              </div>
            ) : (
              notifications.map((n) => {
                const isUnread = !n.readAt;
                const SourceIcon = SOURCE_ICONS[n.source] || Bell;
                const dotColor = PRIORITY_COLORS[n.priority] || PRIORITY_COLORS.medium;
                return (
                  <div
                    key={n.id}
                    className={`px-4 py-3 transition-colors ${isUnread ? 'bg-blue-50/40' : 'hover:bg-gray-50'}`}
                    data-testid={`notification-item-${n.id}`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="relative flex-shrink-0 mt-0.5">
                        <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center">
                          <SourceIcon className="w-4 h-4 text-gray-600" />
                        </div>
                        <span className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ${dotColor} ring-2 ring-white`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm truncate ${isUnread ? 'font-semibold text-gray-900' : 'font-medium text-gray-700'}`}>
                          {n.title}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                          {n.message}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-[10px] text-gray-400">{timeAgo(n.createdAt)}</span>
                          {n.asset && (
                            <span className="text-[10px] font-medium text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                              {n.asset}
                            </span>
                          )}
                        </div>
                      </div>
                      {isUnread && (
                        <button
                          onClick={(e) => handleMarkRead(n.id, e)}
                          className="p-1 hover:bg-gray-200 rounded transition-colors flex-shrink-0"
                          title="Mark as read"
                          data-testid={`mark-read-${n.id}`}
                        >
                          <Check className="w-3.5 h-3.5 text-gray-400" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2.5 border-t border-gray-100 bg-gray-50/50">
            <Link
              to="/notifications"
              onClick={() => setIsOpen(false)}
              className="block text-center text-sm text-blue-600 hover:text-blue-700 font-medium"
              data-testid="view-all-notifications-link"
            >
              View all notifications
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
