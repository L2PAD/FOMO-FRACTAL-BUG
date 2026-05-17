/**
 * AdminAuthContext — ISOLATED admin auth state.
 *
 * Architectural invariant: admin secret state lives ONLY inside this
 * provider.  It is NEVER pushed into Zustand, global stores, redux,
 * URL fragments, query params, console logs or any other surface that
 * could persist or leak it.
 *
 * Storage:
 *   * SecureStore on native (never reached — admin is web-only) and
 *     localStorage with a dedicated key on web (the only deployment
 *     target).  Both are wrapped behind the same async API so the
 *     provider does not branch on Platform.
 *
 *   * The secret itself is stored.  The activity timestamp is stored
 *     separately so an inactivity sweep can drop the secret without
 *     having to re-decrypt or re-read.
 *
 * Lifetime:
 *   * 8 hours of inactivity → secret is wiped, user lands on /admin/login.
 *   * Activity is refreshed on every successful adminClient request,
 *     every navigation event, and every mutation.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Platform } from 'react-native';
import { bindAdminAuth } from '../api/adminClient';

const STORAGE_KEY = 'fomo.admin.secret.v1';
const ACTIVITY_KEY = 'fomo.admin.activity.v1';
const INACTIVITY_MS = 8 * 60 * 60 * 1000; // 8 hours
const SWEEP_INTERVAL_MS = 60 * 1000;       // check every minute

// ── Storage adapter (web-only — admin never mounts on native) ──────
const storage = {
  async get(key: string): Promise<string | null> {
    if (Platform.OS !== 'web') return null;
    try {
      return window.localStorage.getItem(key);
    } catch { return null; }
  },
  async set(key: string, value: string) {
    if (Platform.OS !== 'web') return;
    try { window.localStorage.setItem(key, value); } catch {}
  },
  async del(key: string) {
    if (Platform.OS !== 'web') return;
    try { window.localStorage.removeItem(key); } catch {}
  },
};

export interface AdminAuthState {
  ready: boolean;            // initial hydration finished
  authenticated: boolean;
  inactivityExpiresAt: number | null;
  login: (secret: string) => Promise<{ ok: boolean; error?: string }>;
  logout: () => Promise<void>;
  touch: () => void;         // refresh activity timestamp
  getSecret: () => string | null;   // adminClient reads this on each request
}

const AdminAuthContext = createContext<AdminAuthState | null>(null);

export function AdminAuthProvider({ children }: { children: React.ReactNode }) {
  // ── Synchronous hydration from localStorage (web-only domain).
  // The original async hydrate() introduced a race: children mounted and
  // fired their first authenticated request BEFORE the JWT was loaded,
  // landing them on a 401.  localStorage on web is fully synchronous, so
  // we can resolve the initial auth state during the lazy-state init.
  const initialAuth = useMemo(() => {
    if (Platform.OS !== 'web') return { secret: null as string | null, expiresAt: null as number | null };
    try {
      const s = window.localStorage.getItem(STORAGE_KEY);
      const lastActStr = window.localStorage.getItem(ACTIVITY_KEY);
      const lastAct = parseInt(lastActStr || '0', 10);
      if (s && lastAct && Date.now() - lastAct < INACTIVITY_MS) {
        return { secret: s, expiresAt: lastAct + INACTIVITY_MS };
      }
      // expired — proactively wipe so child code doesn't see stale state
      if (s || lastActStr) {
        try { window.localStorage.removeItem(STORAGE_KEY); } catch {}
        try { window.localStorage.removeItem(ACTIVITY_KEY); } catch {}
      }
    } catch {}
    return { secret: null, expiresAt: null };
  }, []);

  // The secret never goes into React state — only a presence flag does.
  // This keeps the secret out of devtools tree snapshots.
  const secretRef = useRef<string | null>(initialAuth.secret);
  const [authenticated, setAuthenticated] = useState(!!initialAuth.secret);
  const [ready, setReady] = useState(true); // synchronous hydration → ready immediately
  const [inactivityExpiresAt, setExpiry] = useState<number | null>(initialAuth.expiresAt);

  const hydrate = useCallback(async () => {
    const [s, lastAct] = await Promise.all([
      storage.get(STORAGE_KEY),
      storage.get(ACTIVITY_KEY),
    ]);
    if (s && lastAct) {
      const lastActMs = parseInt(lastAct, 10) || 0;
      const age = Date.now() - lastActMs;
      if (age < INACTIVITY_MS) {
        secretRef.current = s;
        setAuthenticated(true);
        setExpiry(lastActMs + INACTIVITY_MS);
      } else {
        // expired — wipe
        await Promise.all([storage.del(STORAGE_KEY), storage.del(ACTIVITY_KEY)]);
        secretRef.current = null;
        setAuthenticated(false);
      }
    }
    setReady(true);
  }, []);

  useEffect(() => { hydrate(); }, [hydrate]);

  // Inactivity sweep — runs even when no API calls happen, so an idle
  // tab still loses access on the 8h boundary without a refresh.
  useEffect(() => {
    if (!authenticated) return;
    const id = setInterval(async () => {
      const lastActStr = await storage.get(ACTIVITY_KEY);
      const lastAct = parseInt(lastActStr || '0', 10);
      if (!lastAct || Date.now() - lastAct >= INACTIVITY_MS) {
        await Promise.all([storage.del(STORAGE_KEY), storage.del(ACTIVITY_KEY)]);
        secretRef.current = null;
        setAuthenticated(false);
        setExpiry(null);
      }
    }, SWEEP_INTERVAL_MS);
    return () => clearInterval(id);
  }, [authenticated]);

  const touch = useCallback(() => {
    const now = Date.now();
    storage.set(ACTIVITY_KEY, String(now));
    setExpiry(now + INACTIVITY_MS);
  }, []);

  const login = useCallback(async (secret: string) => {
    const trimmed = (secret || '').trim();
    if (!trimmed) return { ok: false, error: 'Secret is required' };
    // Exchange the shared secret for a short-lived role=admin JWT.
    // The secret itself never gets persisted — only the JWT does, which
    // carries its own server-side exp and is gone after 8h regardless.
    try {
      const base = (process.env.EXPO_PUBLIC_BACKEND_URL || '').replace(/\/+$/, '');
      // NOTE [TIER-REINTEGRATE.0]: this orphan Expo admin uses the
      // operator-secret auth path.  The canonical FOMO admin login at
      // /api/admin/auth/login expects {username, password} and is
      // owned by the precompiled FOMO Intelligence Terminal SPA.
      const r = await fetch(`${base}/api/admin/operator-auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret: trimmed }),
      });
      if (r.status === 401) {
        return { ok: false, error: 'Invalid admin secret' };
      }
      if (!r.ok) return { ok: false, error: `Server returned ${r.status}` };
      const data = await r.json();
      const token: string | undefined = data?.token;
      if (!token) return { ok: false, error: 'Malformed login response' };
      secretRef.current = token;   // we now carry the JWT, not the raw secret
      const now = Date.now();
      await Promise.all([
        storage.set(STORAGE_KEY, token),
        storage.set(ACTIVITY_KEY, String(now)),
      ]);
      setAuthenticated(true);
      setExpiry(now + INACTIVITY_MS);
      return { ok: true };
    } catch (e: any) {
      return { ok: false, error: e?.message || 'Network error' };
    }
  }, []);

  const logout = useCallback(async () => {
    await Promise.all([storage.del(STORAGE_KEY), storage.del(ACTIVITY_KEY)]);
    secretRef.current = null;
    setAuthenticated(false);
    setExpiry(null);
  }, []);

  const getSecret = useCallback(() => secretRef.current, []);

  // Bind the adminClient interceptor SYNCHRONOUSLY during render so that
  // any descendant which fires a request on its first useEffect already
  // sees a populated Authorization header. Doing this in useEffect causes
  // a child-vs-parent effect ordering race on hard navigation (operators
  // happened to win it, billing happened to lose it). Render-phase bind
  // is safe here because bindAdminAuth is an idempotent assignment of two
  // function references — no React state is mutated.
  bindAdminAuth(getSecret, touch);

  const value = useMemo<AdminAuthState>(() => ({
    ready, authenticated, inactivityExpiresAt,
    login, logout, touch, getSecret,
  }), [ready, authenticated, inactivityExpiresAt, login, logout, touch, getSecret]);

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
}

export function useAdminAuth(): AdminAuthState {
  const ctx = useContext(AdminAuthContext);
  if (!ctx) throw new Error('useAdminAuth must be used inside AdminAuthProvider');
  return ctx;
}
