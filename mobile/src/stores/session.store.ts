import { create } from 'zustand';
import { api } from '../services/api/api-client';
import { registerAuthBridge } from '../core/auth/auth-bridge';

/**
 * session.store.ts — owner of authentication state.
 *
 * After Task 5 (2026-05-12) the legacy circular import between this store
 * and `api-client.ts` has been broken. The api-client no longer imports
 * this store directly. Instead it reads tokens and mutates the session via
 * the neutral `auth-bridge`, and this store registers a bridge impl after
 * `create()` returns.
 *
 * Module graph (post-fix):
 *
 *     session.store ─▶ api-client ─▶ auth-bridge
 *              │                          ▲
 *              └──────────────────────────┘
 *
 * Three-node DAG, no cycle. Cold-start token reads are deterministic
 * because the bridge function pointer is installed by the same module
 * eval pass that creates the zustand store, so any later importer of
 * `useSessionStore` is guaranteed to see a fully wired auth surface.
 */

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatarUrl?: string | null;
  plan: 'FREE' | 'PRO' | 'INSTITUTIONAL';
  planStatus?: string;
  authProviders?: { google: boolean; email: boolean; telegram: boolean };
  linkedApps?: { web: boolean; miniapp: boolean; mobile: boolean };
  subscription?: any;
  access?: any;
  preferences?: any;
  referrals?: any;
  stats?: any;
}

interface SessionState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isHydrated: boolean;
  isLoading: boolean;

  setSession: (payload: {
    user: AuthUser;
    accessToken: string;
    refreshToken: string;
  }) => void;
  clearSession: () => void;
  setHydrated: (value: boolean) => void;
  setLoading: (value: boolean) => void;
  refreshUser: () => Promise<void>;
  upgradeToPro: () => void;
  downgradeToFree: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isHydrated: false,
  isLoading: false,

  setSession: ({ user, accessToken, refreshToken }) =>
    set({ user, accessToken, refreshToken }),

  clearSession: () =>
    set({ user: null, accessToken: null, refreshToken: null }),

  setHydrated: (value) => set({ isHydrated: value }),
  setLoading: (value) => set({ isLoading: value }),

  // Refresh user data from server (after checkout, profile update, etc.)
  refreshUser: async () => {
    try {
      const { data } = await api.get('/mobile/profile');
      const current = get().user;
      if (current && data) {
        set({
          user: {
            ...current,
            plan: data.plan || current.plan,
            planStatus: data.planStatus,
            subscription: data.subscription,
            access: data.access,
            name: data.name || current.name,
            email: data.email || current.email,
            preferences: data.preferences,
            authProviders: data.authProviders,
          },
        });
      }
    } catch {}
  },

  upgradeToPro: () =>
    set((state) => ({
      user: state.user ? { ...state.user, plan: 'PRO' as const } : null,
    })),

  downgradeToFree: () =>
    set((state) => ({
      user: state.user ? { ...state.user, plan: 'FREE' as const } : null,
    })),
}));

// ─── auth-bridge registration ───────────────────────────────────────────
// Wires the transport layer (`api-client.ts`) to this store WITHOUT
// requiring the transport to import the store. The bridge is installed
// synchronously at module evaluation time, so any subsequent api request
// sees the live zustand state.
registerAuthBridge({
  getAccessToken: () => useSessionStore.getState().accessToken,
  getRefreshToken: () => useSessionStore.getState().refreshToken,
  setSession: (payload) => useSessionStore.getState().setSession(payload),
  clearSession: () => useSessionStore.getState().clearSession(),
  // TIER-2: deterministic identity for the `X-User-Id` fallback header.
  // Returns the user's email or numeric id when logged in; null otherwise
  // (api-client substitutes `dev_user` so the seeded dev principal still
  // resolves capabilities cleanly in the local sandbox).
  getUserIdentity: () => {
    const u = useSessionStore.getState().user;
    if (!u) return null;
    return (u.email || (u as any).id || null) as string | null;
  },
});
