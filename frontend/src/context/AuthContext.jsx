/**
 * Auth Context — Emergent Google OAuth
 *
 * Provides:
 * - user state (null | user object)
 * - login() — redirects to Emergent OAuth
 * - logout()
 * - isAuthenticated, isPro, isFree
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

const API = process.env.REACT_APP_BACKEND_URL;
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  // CRITICAL: useRef prevents double-processing in React StrictMode
  const hasProcessedSession = useRef(false);
  const isExchanging = useRef(false);

  // Unified auth initialization: process session_id OR check existing session
  useEffect(() => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const hash = window.location.hash;

    if (hash && hash.includes('session_id=') && !hasProcessedSession.current) {
      // OAuth callback: exchange session_id for persistent session
      hasProcessedSession.current = true;
      isExchanging.current = true;
      const params = new URLSearchParams(hash.replace('#', ''));
      const sessionId = params.get('session_id');
      // Clean URL immediately
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
      if (sessionId) {
        exchangeSession(sessionId);
      } else {
        setLoading(false);
      }
    } else if (!isExchanging.current) {
      // Normal page load: check existing session cookie
      checkSession();
    }
  }, []);

  const checkSession = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/auth/me`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
      }
    } catch (e) {
      // Not authenticated
    } finally {
      setLoading(false);
    }
  }, []);

  const exchangeSession = async (sessionId) => {
    try {
      console.log('[Auth] Exchanging session_id...');
      const res = await fetch(`${API}/api/auth/session`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (res.ok) {
        const data = await res.json();
        console.log('[Auth] Session exchanged, user:', data.user?.email);
        setUser(data.user);

        // Auto-apply referral code from localStorage
        const refCode = localStorage.getItem('referral_code');
        if (refCode) {
          try {
            await fetch(`${API}/api/billing/apply-referral`, {
              method: 'POST',
              credentials: 'include',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ code: refCode }),
            });
            localStorage.removeItem('referral_code');
          } catch (e) {
            console.error('[Auth] Referral apply error:', e);
          }
        }
      } else {
        console.error('[Auth] Exchange failed:', res.status);
        await checkSession();
      }
    } catch (e) {
      console.error('[Auth] Session exchange error:', e);
    } finally {
      isExchanging.current = false;
      setLoading(false);
    }
  };

  const login = useCallback(() => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/exchange';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch(`${API}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch (e) {
      // Ignore
    }
    setUser(null);
  }, []);

  const value = {
    user,
    loading,
    login,
    logout,
    isAuthenticated: !!user,
    isPro: user?.plan_status === 'active',
    isFree: !user || user?.plan_status === 'free' || user?.plan_status === 'canceled',
    refreshUser: checkSession,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be within AuthProvider');
  return context;
}
