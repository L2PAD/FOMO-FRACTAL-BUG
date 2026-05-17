/**
 * NotificationsPage — Full notification feed with filters
 * Unified Notification Engine UI
 */
import { useState, useEffect, useCallback } from 'react';
import { Bell, Check, CheckCheck, Filter, TrendingDown, Globe, Activity, Zap, Server, RefreshCw } from 'lucide-react';
import * as notificationsApi from '../api/notifications.api';

const SOURCE_ICONS = {
  exchange: TrendingDown,
  onchain: Globe,
  sentiment: Activity,
  fractal: Zap,
  telegram: Zap,
  system: Server,
};

const SOURCE_LABELS = {
  exchange: 'Exchange',
  onchain: 'OnChain',
  sentiment: 'Sentiment',
  fractal: 'Fractal',
  telegram: 'Telegram',
  system: 'System',
};

const PRIORITY_STYLES = {
  critical: { dot: 'bg-red-500', bg: 'bg-red-50', text: 'text-red-700', label: 'Critical' },
  high: { dot: 'bg-orange-500', bg: 'bg-orange-50', text: 'text-orange-700', label: 'High' },
  medium: { dot: 'bg-blue-500', bg: 'bg-blue-50', text: 'text-blue-700', label: 'Medium' },
  low: { dot: 'bg-gray-400', bg: 'bg-gray-50', text: 'text-gray-600', label: 'Low' },
};

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all | unread | source filter
  const [stats, setStats] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [feedRes, statsRes] = await Promise.all([
        notificationsApi.getFeed('user', 50),
        notificationsApi.getNotificationStats(),
      ]);
      if (feedRes?.ok) {
        setNotifications(feedRes.notifications || []);
        setUnreadCount(feedRes.unread || 0);
      }
      if (statsRes?.ok) setStats(statsRes.stats);
    } catch (err) {
      console.error('Load notifications failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleMarkRead = async (id) => {
    await notificationsApi.markAsRead(id);
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, readAt: new Date().toISOString() } : n));
    setUnreadCount(prev => Math.max(0, prev - 1));
  };

  const handleMarkAllRead = async () => {
    await notificationsApi.markAllRead('user');
    setNotifications(prev => prev.map(n => ({ ...n, readAt: new Date().toISOString() })));
    setUnreadCount(0);
  };

  const timeAgo = (dateStr) => {
    if (!dateStr) return '';
    const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const filtered = notifications.filter(n => {
    if (filter === 'unread') return !n.readAt;
    if (filter !== 'all') return n.source === filter;
    return true;
  });

  const sources = [...new Set(notifications.map(n => n.source).filter(Boolean))];

  return (
    <div data-testid="notifications-page">
      {/* Header — unified style */}
      <div className="border-b border-gray-200 bg-white h-[71px]">
        <div className="px-6 h-full flex items-center">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-3">
              <Bell className="w-5 h-5 text-gray-400" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">Notifications</h1>
                <p className="text-xs text-gray-400">
                  {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
                  {stats && ` | ${stats.total} total`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  data-testid="mark-all-read-btn"
                >
                  <CheckCheck className="w-4 h-4" />
                  Mark all read
                </button>
              )}
              <button
                onClick={loadData}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                data-testid="refresh-notifications-btn"
              >
                <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="px-6 py-6">
      {/* Filters */}
      <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1" data-testid="notification-filters">
        <FilterChip active={filter === 'all'} onClick={() => setFilter('all')} label="All" />
        <FilterChip active={filter === 'unread'} onClick={() => setFilter('unread')} label={`Unread (${unreadCount})`} />
        {sources.map(s => (
          <FilterChip
            key={s}
            active={filter === s}
            onClick={() => setFilter(s)}
            label={SOURCE_LABELS[s] || s}
            icon={SOURCE_ICONS[s]}
          />
        ))}
      </div>

      {/* Notification List */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100" data-testid="notification-list">
        {loading && notifications.length === 0 ? (
          <div className="p-12 text-center">
            <RefreshCw className="w-6 h-6 animate-spin text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-gray-500">Loading notifications...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <Bell className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-500">
              {filter === 'unread' ? 'No unread notifications' : 'No notifications'}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Events from Exchange, OnChain, Sentiment and more will appear here
            </p>
          </div>
        ) : (
          filtered.map((n) => (
            <NotificationRow key={n.id} notification={n} onMarkRead={handleMarkRead} timeAgo={timeAgo} />
          ))
        )}
      </div>
      </div>
    </div>
  );
}

function FilterChip({ active, onClick, label, icon: Icon }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
        active
          ? 'bg-gray-900 text-white'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
    >
      {Icon && <Icon className="w-3.5 h-3.5" />}
      {label}
    </button>
  );
}

function NotificationRow({ notification: n, onMarkRead, timeAgo }) {
  const isUnread = !n.readAt;
  const SourceIcon = SOURCE_ICONS[n.source] || Bell;
  const pStyle = PRIORITY_STYLES[n.priority] || PRIORITY_STYLES.medium;

  return (
    <div
      className={`px-4 py-3.5 flex items-start gap-3 transition-colors ${isUnread ? 'bg-blue-50/30' : 'hover:bg-gray-50'}`}
      data-testid={`notification-row-${n.id}`}
    >
      <div className="relative flex-shrink-0 mt-0.5">
        <div className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center">
          <SourceIcon className="w-4.5 h-4.5 text-gray-600" />
        </div>
        <span className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ${pStyle.dot} ring-2 ring-white`} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className={`text-sm truncate ${isUnread ? 'font-semibold text-gray-900' : 'font-medium text-gray-700'}`}>
            {n.title}
          </p>
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${pStyle.bg} ${pStyle.text}`}>
            {pStyle.label}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5">{n.message}</p>
        <div className="flex items-center gap-2 mt-1.5">
          <span className="text-[10px] text-gray-400">{timeAgo(n.createdAt)}</span>
          {n.asset && (
            <span className="text-[10px] font-medium text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">{n.asset}</span>
          )}
          <span className="text-[10px] text-gray-400">{SOURCE_LABELS[n.source] || n.source}</span>
        </div>
      </div>

      {isUnread && (
        <button
          onClick={() => onMarkRead(n.id)}
          className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors flex-shrink-0"
          title="Mark as read"
          data-testid={`mark-read-${n.id}`}
        >
          <Check className="w-4 h-4 text-gray-400" />
        </button>
      )}
    </div>
  );
}
