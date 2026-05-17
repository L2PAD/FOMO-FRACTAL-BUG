/**
 * P1 Web Soft Gate — access store & hook.
 * 
 * Backend is the single source of truth. Frontend just renders what
 * `/api/access/preview` says.
 * 
 * This store is platform-agnostic (works on iOS/Android/Web). On mobile,
 * `<GatedBlock>` defaults to pass-through, so the access matrix only
 * actually gates Web. Mobile still gets a correct level for analytics.
 */
import { create } from 'zustand';
import { Platform } from 'react-native';
import { api } from '../services/api/api-client';

export type AccessLevel = 'guest' | 'auth_free' | 'pro';

export interface AccessBlock {
  visible: boolean;
  locked: boolean;
  unlock_reason: 'auth_required' | 'pro_required' | null;
  cta: string | null;
  limit?: number;
}

export interface AccessBlocks {
  decision: AccessBlock;
  prediction_snapshot: AccessBlock;
  market_state: AccessBlock;
  drivers_preview: AccessBlock;
  drivers_full: AccessBlock;
  prediction_details: AccessBlock;
  full_breakdown: AccessBlock;
  feed_detail: AccessBlock;
  history_stats: AccessBlock;
  entry: AccessBlock;
  invalidation: AccessBlock;
  target: AccessBlock;
  [k: string]: AccessBlock;
}

interface AccessState {
  level: AccessLevel;
  authenticated: boolean;
  user_id: string | null;
  email: string | null;
  plan: string;
  blocks: AccessBlocks | null;
  feature_enabled: boolean;
  loaded: boolean;
  loading: boolean;
  error: string | null;
  guestSessionId: string | null;
  fetchPreview: () => Promise<void>;
  ensureGuestSession: () => string;
  trackEvent: (event: string, params?: Record<string, any>) => void;
  mergeGuestSession: () => Promise<void>;
  reset: () => void;
}

const GUEST_SESSION_KEY = 'fomo_guest_session_id';

function _genGuestSessionId(): string {
  const r = (typeof crypto !== 'undefined' && (crypto as any).randomUUID)
    ? (crypto as any).randomUUID().replace(/-/g, '').slice(0, 20)
    : Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  return `g_${r}`;
}

function _readStoredGuestSession(): string | null {
  if (Platform.OS !== 'web') return null;
  try {
    if (typeof sessionStorage !== 'undefined') {
      return sessionStorage.getItem(GUEST_SESSION_KEY);
    }
  } catch {}
  return null;
}

function _writeStoredGuestSession(id: string) {
  if (Platform.OS !== 'web') return;
  try {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(GUEST_SESSION_KEY, id);
    }
  } catch {}
}

export const useAccessStore = create<AccessState>((set, get) => ({
  level: 'guest',
  authenticated: false,
  user_id: null,
  email: null,
  plan: 'FREE',
  blocks: null,
  feature_enabled: true,
  loaded: false,
  loading: false,
  error: null,
  guestSessionId: _readStoredGuestSession(),

  ensureGuestSession() {
    const existing = get().guestSessionId;
    if (existing) return existing;
    const id = _genGuestSessionId();
    _writeStoredGuestSession(id);
    set({ guestSessionId: id });
    return id;
  },

  async fetchPreview() {
    if (get().loading) return;
    set({ loading: true, error: null });
    try {
      const res = await api.get('/api/access/preview');
      const d = res.data || {};
      set({
        level: d.level || 'guest',
        authenticated: !!d.authenticated,
        user_id: d.user_id || null,
        email: d.email || null,
        plan: d.plan || 'FREE',
        blocks: d.blocks || null,
        feature_enabled: !!d.feature_enabled,
        loaded: true,
        loading: false,
      });
    } catch (err: any) {
      set({ loading: false, error: err?.message || 'failed' });
    }
  },

  trackEvent(event, params = {}) {
    // Only track on web — mobile has its own telemetry stack.
    if (Platform.OS !== 'web') return;
    const gsid = get().ensureGuestSession();
    const body = {
      event,
      guest_session_id: gsid,
      platform: 'web',
      ...params,
    };
    // Fire-and-forget — don't block UI.
    api.post('/api/access/track', body).catch(() => {});
  },

  async mergeGuestSession() {
    const gsid = get().guestSessionId;
    if (!gsid) return;
    try {
      await api.post('/api/access/merge-guest', { guest_session_id: gsid });
    } catch {}
  },

  reset() {
    set({
      level: 'guest',
      authenticated: false,
      user_id: null,
      email: null,
      plan: 'FREE',
      blocks: null,
      loaded: false,
      loading: false,
      error: null,
    });
  },
}));

/**
 * Hook entry point. Fetches preview on first mount, returns current state.
 */
export function useAccessLevel() {
  const state = useAccessStore((s) => ({
    level: s.level,
    authenticated: s.authenticated,
    blocks: s.blocks,
    loaded: s.loaded,
    loading: s.loading,
    fetchPreview: s.fetchPreview,
    trackEvent: s.trackEvent,
    isWebGate: Platform.OS === 'web' && s.feature_enabled,
  }));
  return state;
}

/**
 * Returns access info for a single block. Safe default (visible=true) when
 * payload hasn't loaded yet OR we're on mobile — pass-through behaviour.
 */
export function useAccessBlock(blockKey: keyof AccessBlocks | string): AccessBlock {
  const { blocks } = useAccessStore((s) => ({ blocks: s.blocks }));
  // On mobile we NEVER gate via this store — return pass-through.
  if (Platform.OS !== 'web') {
    return { visible: true, locked: false, unlock_reason: null, cta: null };
  }
  if (!blocks) {
    return { visible: true, locked: false, unlock_reason: null, cta: null };
  }
  return blocks[blockKey as string] || { visible: true, locked: false, unlock_reason: null, cta: null };
}
