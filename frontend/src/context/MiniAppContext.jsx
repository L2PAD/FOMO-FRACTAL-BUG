import { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL;

const MiniAppContext = createContext(null);

const STORAGE_KEY = 'miniapp_state';

function loadPersisted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return {};
}

function persist(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      selectedAsset: state.selectedAsset,
      recentAssets: state.recentAssets,
      favoriteAssets: state.favoriteAssets,
      panelAssets: state.panelAssets,
      activeTab: state.activeTab,
      theme: state.theme,
    }));
  } catch {}
}

export function MiniAppProvider({ children }) {
  const saved = loadPersisted();

  const [selectedAsset, setSelectedAssetRaw] = useState(saved.selectedAsset || 'BTC');
  const [recentAssets, setRecentAssets] = useState(saved.recentAssets || ['BTC', 'ETH', 'SOL']);
  const [favoriteAssets, setFavoriteAssets] = useState(saved.favoriteAssets || ['BTC', 'ETH', 'SOL']);
  const [panelAssets, setPanelAssets] = useState(saved.panelAssets || ['BTC', 'ETH', 'SOL']);
  const [activeTab, setActiveTab] = useState(saved.activeTab || 'home');
  const [theme, setTheme] = useState(saved.theme || 'dark');
  const [homeData, setHomeData] = useState(null);
  const [homeLoading, setHomeLoading] = useState(true);
  const [feedData, setFeedData] = useState(null);
  const [polyData, setPolyData] = useState(null);
  const [edgeData, setEdgeData] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [telegramId, setTelegramId] = useState('');
  const [telegramUser, setTelegramUser] = useState(null);
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [paywallReason, setPaywallReason] = useState('default');

  // ── Event Tracking ──
  const trackEvent = useCallback(async (event, meta = {}) => {
    try {
      const uid = telegramId || `anon_${Math.random().toString(36).slice(2, 10)}`;
      const seed = [...String(uid)].reduce((a, c) => a + c.charCodeAt(0), 0) % 100;
      const variant = seed < 25 ? 'A' : seed < 50 ? 'B' : seed < 75 ? 'C' : 'D';
      fetch(`${API}/api/miniapp/ab/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: uid, event, variant, meta }),
      }).catch(() => {});
    } catch {}
  }, [telegramId]);

  // Detect telegram user
  useEffect(() => {
    try {
      const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
      if (tgUser?.id) {
        setTelegramId(String(tgUser.id));
        setTelegramUser({
          id: String(tgUser.id),
          firstName: tgUser.first_name || '',
          lastName: tgUser.last_name || '',
          username: tgUser.username || '',
          photoUrl: tgUser.photo_url || '',
        });
        // Sync Telegram user data to backend
        fetch(`${API}/api/miniapp/sync-telegram-user`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            telegram_id: String(tgUser.id),
            first_name: tgUser.first_name || '',
            last_name: tgUser.last_name || '',
            username: tgUser.username || '',
            photo_url: tgUser.photo_url || '',
          }),
        }).catch(() => {});
      }
    } catch {}

    // Handle deep link params (?tab=edge&asset=BTC)
    try {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      const asset = params.get('asset');
      const fromAlert = tab || asset;
      if (tab) setActiveTab(tab === 'edge' ? 'polymarket' : tab);
      if (asset) setSelectedAssetRaw(asset.toUpperCase());
      // Track alert_opened if came from deep link (once per session)
      if (fromAlert && !sessionStorage.getItem('_dl_tracked')) {
        sessionStorage.setItem('_dl_tracked', '1');
        setTimeout(() => {
          const uid = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
          const id = uid ? String(uid) : `anon_${Math.random().toString(36).slice(2, 10)}`;
          const seed = [...String(id)].reduce((a, c) => a + c.charCodeAt(0), 0) % 100;
          const v = seed < 25 ? 'A' : seed < 50 ? 'B' : seed < 75 ? 'C' : 'D';
          fetch(`${API}/api/miniapp/ab/track`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: id, event: 'alert_opened', variant: v, meta: { tab: tab || 'home', asset: asset || 'BTC' } }),
          }).catch(() => {});
        }, 500);
      }
    } catch {}
  }, []);

  const setSelectedAsset = useCallback((asset) => {
    setSelectedAssetRaw(asset);
    setHomeData(null);
    setHomeLoading(true);
    // Add to panel if not there (max 5)
    setPanelAssets(prev => {
      if (prev.includes(asset)) return prev;
      if (prev.length >= 5) return [...prev.slice(1), asset];
      return [...prev, asset];
    });
    setRecentAssets(prev => {
      const next = [asset, ...prev.filter(a => a !== asset)].slice(0, 8);
      return next;
    });
  }, []);

  const removeFromPanel = useCallback((asset) => {
    setPanelAssets(prev => {
      const next = prev.filter(a => a !== asset);
      if (asset === selectedAsset && next.length > 0) {
        setSelectedAssetRaw(next[0]);
        setHomeData(null);
        setHomeLoading(true);
      }
      return next;
    });
  }, [selectedAsset]);

  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  }, []);

  // Fetch home data when asset changes
  const fetchHome = useCallback(async () => {
    setHomeLoading(true);
    try {
      const res = await fetch(`${API}/api/miniapp/home?asset=${selectedAsset}`);
      const json = await res.json();
      if (json.ok) setHomeData(json);
    } catch {}
    setHomeLoading(false);
  }, [selectedAsset]);

  useEffect(() => {
    fetchHome();
    const iv = setInterval(fetchHome, 60000);
    return () => clearInterval(iv);
  }, [fetchHome]);

  // Fetch feed (lazy)
  const fetchFeed = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/miniapp/feed?limit=30`);
      const json = await res.json();
      if (json.ok) setFeedData(json);
    } catch {}
  }, []);

  // Fetch polymarket (lazy)
  const fetchPoly = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/miniapp/polymarket`);
      const json = await res.json();
      if (json.ok) setPolyData(json);
    } catch {}
  }, []);

  // Fetch edge (lazy)
  const fetchEdge = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/miniapp/edge`);
      const json = await res.json();
      if (json.ok) setEdgeData(json);
    } catch {}
  }, []);

  // Fetch profile (lazy)
  const fetchProfile = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/miniapp/profile?telegram_id=${telegramId}`);
      const json = await res.json();
      if (json.ok) setProfileData(json);
    } catch {}
  }, [telegramId]);

  // Favorites API
  const addFavorite = useCallback(async (asset) => {
    try {
      await fetch(`${API}/api/miniapp/favorites/add`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_id: telegramId, asset }),
      });
      setFavoriteAssets(prev => [...new Set([...prev, asset])]);
      fetchProfile();
    } catch {}
  }, [telegramId, fetchProfile]);

  const removeFavorite = useCallback(async (asset) => {
    try {
      await fetch(`${API}/api/miniapp/favorites/remove`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_id: telegramId, asset }),
      });
      setFavoriteAssets(prev => prev.filter(a => a !== asset));
      fetchProfile();
    } catch {}
  }, [telegramId, fetchProfile]);

  // Settings API
  const updateSettings = useCallback(async (settings) => {
    try {
      await fetch(`${API}/api/miniapp/settings`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_id: telegramId, ...settings }),
      });
      fetchProfile();
    } catch {}
  }, [telegramId, fetchProfile]);

  // Promo API
  const applyPromo = useCallback(async (code) => {
    try {
      const res = await fetch(`${API}/api/miniapp/promo/apply`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_id: telegramId, code }),
      });
      const json = await res.json();
      if (json.ok) fetchProfile();
      return json;
    } catch { return { ok: false, message: 'Network error' }; }
  }, [telegramId, fetchProfile]);

  // Billing APIs
  const [billingData, setBillingData] = useState(null);
  const [plansData, setPlansData] = useState(null);

  const fetchBillingStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/miniapp/billing/status?telegram_id=${telegramId}`);
      const json = await res.json();
      if (json.ok) setBillingData(json);
    } catch {}
  }, [telegramId]);

  const fetchPlans = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/miniapp/billing/plans`);
      const json = await res.json();
      if (json.ok) setPlansData(json);
    } catch {}
  }, []);

  const createCheckout = useCallback(async (interval = 'month') => {
    try {
      const res = await fetch(`${API}/api/miniapp/billing/checkout`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_id: telegramId, origin_url: window.location.origin, interval }),
      });
      const json = await res.json();
      return json;
    } catch { return { ok: false, message: 'Network error' }; }
  }, [telegramId]);

  // CRYPTO PAYMENTS (NOWPayments)
  const createCryptoInvoice = useCallback(async () => {
    try {
      const user_id = telegramId ? `tg_${telegramId}` : null;
      if (!user_id) {
        return { ok: false, message: 'No Telegram ID found' };
      }
      
      const res = await fetch(`${API}/api/payments/create-wallet-invoice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id }),
      });
      const json = await res.json();
      
      if (json.invoice_url) {
        return { ok: true, invoice_url: json.invoice_url, invoice_id: json.invoice_id };
      }
      return { ok: false, message: 'Failed to create invoice' };
    } catch (e) {
      return { ok: false, message: 'Network error' };
    }
  }, [telegramId]);

  const checkPaymentStatus = useCallback(async () => {
    try {
      const user_id = telegramId ? `tg_${telegramId}` : null;
      if (!user_id) return { plan: 'FREE' };
      
      const res = await fetch(`${API}/api/payments/status`, {
        method: 'GET',
        headers: { 'telegram-id': telegramId },
      });
      const json = await res.json();
      return json;
    } catch {
      return { plan: 'FREE' };
    }
  }, [telegramId]);

  const openBillingPortal = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/miniapp/billing/portal`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_id: telegramId, origin_url: window.location.origin }),
      });
      const json = await res.json();
      return json;
    } catch { return { ok: false, message: 'Network error' }; }
  }, [telegramId]);

  const verifyCheckout = useCallback(async (sessionId) => {
    try {
      const res = await fetch(`${API}/api/miniapp/billing/verify/${sessionId}`);
      const json = await res.json();
      if (json.ok && json.success) {
        trackEvent('upgrade_completed', { session_id: sessionId });
        fetchBillingStatus();
        fetchProfile();
      }
      return json;
    } catch { return { ok: false }; }
  }, [fetchBillingStatus, fetchProfile, trackEvent]);

  // Check for billing return URL params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const billing = params.get('billing');
    const sessionId = params.get('session_id');
    if (billing === 'success' && sessionId) {
      verifyCheckout(sessionId);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [verifyCheckout]);


  // 🔥 AUTO PAYWALL TRIGGER - Telegram Mini App
  useEffect(() => {
    if (!profileData?.user) return;
    
    const isExpired = profileData.user.planStatus === 'EXPIRED';
    
    if (isExpired) {
      const expiredAt = profileData.user.expiresAt;
      const now = new Date();
      const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      
      let recentlyExpired = true;
      if (expiredAt) {
        const expiredDate = new Date(expiredAt);
        recentlyExpired = expiredDate > sevenDaysAgo;
      }
      
      // 💣 TRIGGER: Open paywall for recently expired users
      if (recentlyExpired && !sessionStorage.getItem('_expired_paywall_shown')) {
        sessionStorage.setItem('_expired_paywall_shown', '1');
        setTimeout(() => {
          setPaywallReason('expired');
          setPaywallOpen(true);
        }, 1500);
      }
    }
  }, [profileData]);

  // Persist on changes
  useEffect(() => {
    persist({ selectedAsset, recentAssets, favoriteAssets, panelAssets, activeTab, theme });
  }, [selectedAsset, recentAssets, favoriteAssets, panelAssets, activeTab, theme]);

  const value = {
    selectedAsset, setSelectedAsset,
    recentAssets,
    favoriteAssets, setFavoriteAssets,
    panelAssets, removeFromPanel,
    activeTab, setActiveTab,
    theme, toggleTheme,
    homeData, homeLoading, fetchHome,
    feedData, fetchFeed,
    polyData, fetchPoly,
    edgeData, fetchEdge,
    profileData, fetchProfile,
    telegramId,
    telegramUser,
    addFavorite, removeFavorite,
    updateSettings, applyPromo,
    billingData, fetchBillingStatus,
    plansData, fetchPlans,
    createCheckout, openBillingPortal, verifyCheckout,
    createCryptoInvoice, checkPaymentStatus,
    trackEvent,
    paywallOpen, setPaywallOpen,
    paywallReason, setPaywallReason,
  };

  return (
    <MiniAppContext.Provider value={value}>
      {children}
    </MiniAppContext.Provider>
  );
}

export function useMiniApp() {
  const ctx = useContext(MiniAppContext);
  if (!ctx) throw new Error('useMiniApp must be used within MiniAppProvider');
  return ctx;
}
