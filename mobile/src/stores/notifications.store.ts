import { create } from 'zustand';
import { api } from '../services/api/api-client';
import { usePreferencesStore } from './preferences.store';

export interface NotificationItem {
  id: string;
  type: 'SYSTEM' | 'SIGNAL' | 'EDGE' | 'FOMO' | 'PNL_ALERT' | 'WATCHLIST_ALERT';
  title: string;
  body: string;
  data?: {
    asset?: string;
    screen?: string;
    action?: string;
    pnlPct?: number;
    change24h?: number;
    symbol?: string;
    // Push-router bridge fields (CONFIRMED / MISSED / PERSONAL pushes)
    pushType?: 'CONFIRMED' | 'MISSED' | 'PERSONAL' | 'FORMING' | 'TENSION' | string;
    stage?: string;
    direction?: 'bullish' | 'bearish' | 'neutral' | string;
    deepLink?: string;
    startParam?: string;
    ctaLabel?: string;
    sourcesCount?: number | null;
    movePct?: number | null;
    watchersCount?: number | null;
  };
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  icon: string;
  read: boolean;
  createdAt: string;
  readAt?: string | null;
}

interface NotificationsState {
  items: NotificationItem[];
  unreadCount: number;
  unreadSignal: number;
  unreadSystem: number;
  loading: boolean;
  refreshing: boolean;
  tab: 'ALL' | 'PORTFOLIO' | 'EDGE' | 'SIGNAL';
  filter: 'ALL' | 'SIGNAL' | 'SYSTEM';
  setFilter: (f: 'ALL' | 'SIGNAL' | 'SYSTEM') => void;
  setTab: (t: 'ALL' | 'PORTFOLIO' | 'EDGE' | 'SIGNAL') => void;
  fetchNotifications: () => Promise<void>;
  fetchUnreadCount: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  doRefresh: () => Promise<void>;
}

function getLang(): string {
  return usePreferencesStore.getState().language || 'en';
}

export const useNotificationsStore = create<NotificationsState>((set, get) => ({
  items: [],
  unreadCount: 0,
  unreadSignal: 0,
  unreadSystem: 0,
  loading: false,
  refreshing: false,
  tab: 'ALL' as const,
  filter: 'ALL',

  setFilter: (f) => {
    set({ filter: f });
    get().fetchNotifications();
  },

  setTab: (t) => set({ tab: t }),

  doRefresh: async () => {
    set({ refreshing: true });
    await get().fetchNotifications();
    set({ refreshing: false });
  },

  fetchNotifications: async () => {
    try {
      set({ loading: true });
      const filter = get().filter;
      const lang = getLang();
      const params: any = { limit: 50, offset: 0, lang };
      if (filter !== 'ALL') params.type = filter;
      const { data } = await api.get('/api/mobile/notifications', { params });
      set({ items: data.items || [], loading: false });
    } catch (e) {
      set({ loading: false });
    }
  },

  fetchUnreadCount: async () => {
    try {
      const { data } = await api.get('/api/mobile/notifications/unread-count');
      set({
        unreadCount: data.total || 0,
        unreadSignal: data.signal || 0,
        unreadSystem: data.system || 0,
      });
    } catch (e) {
      // silent
    }
  },

  markRead: async (id: string) => {
    try {
      await api.post('/api/mobile/notifications/read', { notificationId: id });
      set((s) => ({
        items: s.items.map((n) => n.id === id ? { ...n, read: true } : n),
        unreadCount: Math.max(0, s.unreadCount - 1),
      }));
    } catch (e) {
      // silent
    }
  },

  markAllRead: async () => {
    try {
      await api.post('/api/mobile/notifications/read-all');
      set((s) => ({
        items: s.items.map((n) => ({ ...n, read: true })),
        unreadCount: 0,
        unreadSignal: 0,
        unreadSystem: 0,
      }));
    } catch (e) {
      // silent
    }
  },
}));
