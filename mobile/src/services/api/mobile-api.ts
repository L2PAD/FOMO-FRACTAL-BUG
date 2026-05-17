import { api } from './api-client';

// ==================== TYPES ====================

export interface HomeData {
  asset: string;
  price: number;
  decision: 'BUY' | 'SELL' | 'WAIT';
  confidence: number;
  strength: 'LOW_EDGE' | 'MODERATE' | 'HIGH';
  mode: 'AGGRESSIVE' | 'STANDARD' | 'DEFENSIVE';
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  marketStory: string;
  range7d: {
    low: number;
    high: number;
  };
  drivers: Driver[];
  timeframeBias: TimeframeBias[];
  liveStatus: {
    ws: boolean;
    quality: 'HIGH' | 'MEDIUM' | 'LOW';
    updatedAt: string;
  };
}

export interface Driver {
  module: string;
  state: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  label: string;
}

export interface TimeframeBias {
  timeframe: string;
  direction: 'bullish' | 'bearish' | 'neutral';
}

export interface FeedItem {
  id: string;
  asset: string;
  source: 'whale' | 'exchange' | 'sentiment' | 'onchain' | 'risk' | 'system' | 'derivatives';
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  impact: 'HIGH' | 'MED' | 'LOW';
  impactPct: number;
  title: string;
  summary: string;
  interpretation: string;
  affectsSignal?: string;
  timestamp: string;
  rawData?: string;
  whyMatters?: string;
  modelInterpretation?: string;
  priority: 'key' | 'secondary' | 'noise';
}

export interface FeedSection {
  label: string;
  items: FeedItem[];
}

export interface IntelOverview {
  asset: string;
  verdict: {
    direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    confidence: number;
    alignedModules: number;
    totalModules: number;
  };
  modules: IntelModule[];
}

export interface IntelModule {
  id: string;
  name: string;
  status: 'ACTIVE' | 'SUN' | 'ERROR';
  direction?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  confidence?: number;
  summary?: string;
  message?: string;
}

export interface EdgeOpportunity {
  id: string;
  question: string;
  category: string;
  marketProb: number;
  modelProb: number;
  edge: number;
  action: 'BUY_YES' | 'BUY_NO' | 'SKIP';
}

export interface EdgeData {
  spotlight?: EdgeOpportunity;
  opportunities: EdgeOpportunity[];
}

export interface ProfileData {
  email: string;
  plan: string;
  memberSince: string;
  watchlist: string[];
  preferences: {
    defaultAsset: string;
    theme: string;
    notifications: boolean;
  };
}

export interface AssetInfo {
  symbol: string;
  name: string;
  category: string;
  rank: number;
  binance: string;
  bybit: string;
}

export interface HistoryItem {
  action: string;
  confidence: number;
  entryPrice: number;
  closePrice: number;
  pnlPct: number;
  outcome: 'WIN' | 'LOSS' | 'FLAT';
  duration: string;
  closedAt: string | null;
  horizon: string;
}

export interface HistoryStats {
  total: number;
  winRate: number | null;
  avgPnlPct: number | null;
  totalPnlPct: number | null;
  signalAccuracy: number | null;
  avgMovePct: number | null;
  highConfWinRate: number | null;
  last5Move: number | null;
  edgeSignals: number | null;
}

export interface MissedSignal {
  asset: string;
  action: string;
  pnlPct: number;
  confidence: number;
  horizon: string;
}

export interface HistoryData {
  asset: string;
  stats: HistoryStats;
  items: HistoryItem[];
  missedSignals: MissedSignal[];
  currentSignal: {
    action: string;
    confidence: number;
    entryPrice: number;
    openedAt: string | null;
    horizon: string;
  } | null;
}

export interface TradingBootstrap {
  status: 'SUN' | 'ACTIVE';
  hasAccess: boolean;
  modules: {
    markets: boolean;
    trade: boolean;
    positions: boolean;
  };
  message?: string;
}

export interface MissedSignalItem {
  id: string;
  asset: string;
  symbol: string;
  action: string;
  confidence: number;
  entryPrice: number;
  closePrice: number;
  pnlPct: number;
  outcome: string;
  entryTs: string | null;
  closeTs: string | null;
  horizon: string;
}

export interface MissedData {
  asset: string;
  count: number;
  avgMovePct: number;
  items: MissedSignalItem[];
}

export interface PushStatusNotification {
  type: string;
  title: string;
  asset: string;
  sentAt: string | null;
}

export interface PushStatus {
  hasToken: boolean;
  tokenCount: number;
  sentToday: number;
  pendingCount: number;
  recentNotifications: PushStatusNotification[];
}

export interface ReferralData {
  code: string;
  invites: number;
  paidReferrals: number;
  earned: string;
  shareUrl: string;
}

export interface GrowthProfile {
  code: string;
  shareUrl: string;
  telegramLink: string;
  season: { id: string; name: string; status: string };
  rank: number;
  seasonScore: number;
  previousRank: number;
  rankDelta: number;
  stats: { clicks: number; signups: number; paidConfirmed: number; paidPending: number };
  milestones: { paid: number; reward: string; label: string; days: number }[];
  nextMilestone: { need: number; paid: number; label: string } | null;
  earnedRewards: { reward_type: string; label: string; status: string }[];
  funnel: { clicks: number; signups: number; payments: number; conversionRate: number };
}

export interface LeaderboardEntry {
  user_id: string;
  name: string;
  email_masked: string;
  score: number;
  rank: number;
  delta: number;
  previous_rank: number;
}

export interface ShareCard {
  asset: string;
  pnl: number;
  message: string;
  cta: string;
  shareText: string;
  shareUrl: string;
  code: string;
}

// 🔥 Signal of the Moment — global top push-signal (hero card on HomeScreen).
// Source of truth: Node.js /api/signals/top (select highest-scored signal from
// push-router notifications in the last 6h). Null when below noise floor.
export interface TopSignal {
  id: string;
  type: string;                 // LISTING | EXPLOIT | ETF | POLY_MISPRICING | NEWS | CONFIRMED | ...
  source: string;               // news | polymarket | sentiment | push_engine
  sourceLabel: string;          // "News" | "Polymarket" | "Listing" | "Exploit" | "ETF" | "Regulation" | "Signal"
  sourceIcon: string;           // emoji for chip
  asset: string | null;         // BTC, BNB, ... or null for market-first (Polymarket, News)
  title: string;                // "BNB move confirmed"
  body: string;                 // "just now · 8 sources aligned · → bullish tilt emerging"
  icon: string;
  confidenceText: string | null;  // muted 1-liner under title ("9 sources aligned · narrative forming")
  sourcesCount: number;           // raw signals contributing — used for "● based on X signals" in Edge
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  priorityScore: number;        // 0..100
  score: number;                // composite rank
  watchersCount: number;
  ctaLabel: string | null;      // "→ See BNB setup"
  deepLink: string | null;
  startParam: string | null;    // news_BNB — used by Telegram Mini App deep link
  createdAt: string;
  ageMinutes: number;           // minutes since push was emitted
  locked: boolean;              // true when Hero Lock kept this signal sticky
  reason: { priority: number; watchers: number; recency: number };
}

// ==================== API FUNCTIONS ====================

export const mobileApi = {
  // HOME
  getHome: async (asset: string = 'BTC'): Promise<HomeData> => {
    const res = await api.get(`/api/mobile/home?asset=${asset}`);
    return res.data;
  },

  // FEED
  getFeed: async (asset?: string): Promise<FeedItem[]> => {
    const url = asset ? `/api/mobile/feed?asset=${asset}` : '/api/mobile/feed';
    const res = await api.get(url);
    return res.data;
  },

  // INTEL
  getIntelOverview: async (asset: string = 'BTC'): Promise<IntelOverview> => {
    const res = await api.get(`/api/mobile/intel?asset=${asset}`);
    return res.data;
  },

  // EDGE
  getEdge: async (asset: string = 'BTC'): Promise<EdgeData> => {
    const res = await api.get(`/api/mobile/edge?asset=${asset}`);
    return res.data;
  },

  // EDGE OPPORTUNITIES (Early Money Engine)
  getEdgeOpportunities: async (asset?: string): Promise<any> => {
    try {
      const params = asset ? `?asset=${asset}` : '';
      const res = await api.get(`/api/mobile/edge/opportunities${params}`);
      return res.data;
    } catch {
      return { ok: false, opportunities: [], count: 0 };
    }
  },

  // PREDICTION MARKETS (Polymarket + MetaBrain overlay)
  getPredictionMarkets: async (limit: number = 20): Promise<any> => {
    try {
      const res = await api.get(`/api/mobile/prediction/markets?limit=${limit}`);
      return res.data;
    } catch {
      return { ok: false, markets: [], count: 0 };
    }
  },

  // 🔥 SIGNAL OF THE MOMENT — global top push-signal for Home hero card.
  // Returns null data when nothing above the noise floor in the last 6h.
  getTopSignal: async (): Promise<{ ok: boolean; data: TopSignal | null }> => {
    try {
      const res = await api.get('/api/signals/top');
      return res.data;
    } catch {
      return { ok: false, data: null };
    }
  },


  // BEHAVIOR TRACKING
  trackEvent: async (eventType: string, data?: Record<string, any>): Promise<void> => {
    try {
      await api.post('/api/mobile/behavior/track', { event_type: eventType, data });
    } catch {}
  },

  // FEED INTELLIGENCE (Feed 2.0)
  getFeedIntelligence: async (asset: string = 'BTC'): Promise<any> => {
    try {
      const res = await api.get(`/api/mobile/feed/intelligence?asset=${asset}`);
      return res.data;
    } catch {
      return { ok: false, mispricing: [], undervalued: [], blindspots: [], developing: [] };
    }
  },

  // VIRTUAL TRADING
  openTrade: async (asset: string, action: string, entryPrice: number, confidence: number, source: string): Promise<any> => {
    try {
      const res = await api.post('/api/mobile/trading/open', {
        asset, action, entry_price: entryPrice, confidence, source,
      });
      return res.data;
    } catch { return { ok: false, error: 'Network error' }; }
  },

  closeTrade: async (positionId: string): Promise<any> => {
    try {
      const res = await api.post('/api/mobile/trading/close', { positionId });
      return res.data;
    } catch { return { ok: false }; }
  },

  getPositions: async (status: string = 'OPEN'): Promise<any> => {
    try {
      const res = await api.get(`/api/mobile/trading/positions?status=${status}`);
      return res.data;
    } catch { return { ok: false, positions: [] }; }
  },

  getPortfolio: async (): Promise<any> => {
    try {
      const res = await api.get('/api/mobile/trading/portfolio');
      return res.data;
    } catch { return null; }
  },

  // CRYPTO PAYMENTS
  createCryptoInvoice: async (): Promise<{ invoice_url: string; invoice_id: string; order_id: string }> => {
    const res = await api.post('/api/payments/create-wallet-invoice');
    return res.data;
  },

  createWalletInvoice: async (_userId?: string): Promise<{ invoice_url: string; payment_id: string; order_id: string }> => {
    const res = await api.post('/api/payments/create-wallet-invoice');
    return {
      invoice_url: res.data.invoice_url,
      payment_id: res.data.invoice_id || res.data.payment_id,
      order_id: res.data.order_id,
    };
  },

  checkPaymentStatus: async (_userId: string, paymentId: string): Promise<{ status: string; user: any }> => {
    const res = await api.get(`/api/payments/status?payment_id=${paymentId}`);
    return res.data;
  },

  getPlans: async (): Promise<any> => {
    const res = await api.get('/api/payments/plans');
    return res.data;
  },

  // PROFILE
  getProfile: async (): Promise<ProfileData> => {
    const res = await api.get('/api/mobile/profile');
    return res.data;
  },

  // ASSETS (Universe)
  getAssets: async (q?: string): Promise<AssetInfo[]> => {
    try {
      const params = q ? `?q=${encodeURIComponent(q)}` : '';
      const res = await api.get(`/api/mobile/assets${params}`);
      return res.data?.assets || [];
    } catch (error) {
      return [];
    }
  },

  // ASSET INTELLIGENCE
  getSystemPicks: async (): Promise<any[]> => {
    try {
      const res = await api.get('/api/mobile/assets/system-picks');
      return res.data?.picks || [];
    } catch { return []; }
  },

  getAssetIntelligence: async (symbol: string): Promise<any> => {
    try {
      const res = await api.get(`/api/mobile/assets/${symbol}/intelligence`);
      return res.data;
    } catch { return { ok: false }; }
  },

  searchAssetsIntel: async (q: string): Promise<any[]> => {
    try {
      const res = await api.get(`/api/mobile/assets/search-intel?q=${encodeURIComponent(q)}`);
      return res.data?.results || [];
    } catch { return []; }
  },

  getWatchlist: async (userId: string = 'dev_user'): Promise<string[]> => {
    try {
      const res = await api.get(`/api/mobile/watchlist?userId=${userId}`);
      return res.data?.assets || [];
    } catch { return []; }
  },

  addToWatchlist: async (symbol: string, userId: string = 'dev_user'): Promise<string[]> => {
    try {
      const res = await api.post(`/api/mobile/watchlist/${symbol}?userId=${userId}`);
      return res.data?.assets || [];
    } catch { return []; }
  },

  removeFromWatchlist: async (symbol: string, userId: string = 'dev_user'): Promise<string[]> => {
    try {
      const res = await api.delete(`/api/mobile/watchlist/${symbol}?userId=${userId}`);
      return res.data?.assets || [];
    } catch { return []; }
  },

  // PORTFOLIO
  getPortfolioPerformance: async (userId: string = 'dev_user'): Promise<any> => {
    try {
      const res = await api.get(`/api/mobile/portfolio/performance?userId=${userId}`);
      return res.data;
    } catch { return { ok: false }; }
  },

  openPortfolio: async (userId: string = 'dev_user'): Promise<any> => {
    try {
      const res = await api.post(`/api/mobile/portfolio/open?userId=${userId}`);
      return res.data;
    } catch { return { ok: false }; }
  },

  updateProfile: async (data: { name?: string }): Promise<any> => {
    try {
      const res = await api.patch('/api/mobile/profile', data);
      return res.data;
    } catch (error) {
      return null;
    }
  },

  // FRACTAL ANALYSIS
  getFractal: async (asset: string = 'BTC'): Promise<any> => {
    try {
      const res = await api.get(`/api/mobile/fractal?asset=${asset}`);
      return res.data;
    } catch (error) {
      return { status: 'no_data', scope: asset };
    }
  },

  // SIGNALS (Decision Engine)
  getSignals: async (horizon: string = 'swing', assets: string = ''): Promise<any> => {
    try {
      const params = new URLSearchParams();
      if (horizon) params.set('horizon', horizon);
      if (assets) params.set('assets', assets);
      const res = await api.get(`/api/mobile/signals?${params.toString()}`);
      return res.data;
    } catch (error) {
      return { ok: false, signals: [] };
    }
  },

  getSignal: async (asset: string, horizon: string = 'swing'): Promise<any> => {
    try {
      const res = await api.get(`/api/mobile/signals/${asset}?horizon=${horizon}`);
      return res.data;
    } catch (error) {
      return { ok: false, signal: null };
    }
  },

  getMarketState: async (): Promise<any> => {
    try {
      const res = await api.get('/api/mobile/market-state');
      return res.data;
    } catch (error) {
      return { ok: false };
    }
  },

  // SENTIMENT
  getSentiment: async (asset: string = 'BTC'): Promise<any> => {
    try {
      const res = await api.get(`/api/mobile/sentiment?asset=${asset}`);
      return res.data;
    } catch (error) {
      return { status: 'no_data', asset };
    }
  },

  triggerSentimentIngestion: async (): Promise<any> => {
    try {
      const res = await api.post('/api/mobile/sentiment/ingest');
      return res.data;
    } catch (error) {
      return { ok: false };
    }
  },

  getFractalAll: async (): Promise<any> => {
    try {
      const res = await api.get('/api/mobile/fractal/all');
      return res.data;
    } catch (error) {
      return { ok: false, scopes: {} };
    }
  },

  updatePreferences: async (prefs: {
    theme?: string;
    language?: string;
    notifications?: boolean | Record<string, boolean>;
  }): Promise<any> => {
    try {
      const res = await api.patch('/api/mobile/profile/preferences', prefs);
      return res.data;
    } catch (error) {
      return null;
    }
  },

  // HISTORY (Track Record)
  getHistory: async (asset: string = 'BTC'): Promise<HistoryData> => {
    try {
      const res = await api.get(`/api/mobile/history?asset=${asset}`);
      return res.data;
    } catch (error) {
      return { asset, stats: { total: 0, winRate: null, avgPnlPct: null, totalPnlPct: null }, items: [], currentSignal: null };
    }
  },

  // MISSED SIGNALS (Honest Engine)
  getMissed: async (asset?: string): Promise<MissedData> => {
    try {
      const params = asset ? `?asset=${asset}` : '';
      const res = await api.get(`/api/mobile/missed${params}`);
      return res.data;
    } catch (error) {
      return { asset: asset || 'ALL', count: 0, avgMovePct: 0, items: [] };
    }
  },

  // USER ACTIVITY TRACKING
  markSeen: async (screen: string = 'home'): Promise<void> => {
    try {
      await api.post('/api/mobile/activity/seen', { screen });
    } catch (error) {
      // Silent fail — non-critical
    }
  },

  // SIGNAL EXPOSURE TRACKING
  markSignalExposure: async (signalId: string, screen: string = 'home'): Promise<void> => {
    try {
      await api.post('/api/mobile/signal-exposure', { signalId, screen });
    } catch (error) {
      // Silent fail — non-critical
    }
  },

  // PUSH NOTIFICATIONS
  registerPushToken: async (pushToken: string, platform: string): Promise<void> => {
    try {
      await api.post('/api/mobile/push/register', { pushToken, platform });
    } catch (error) {
      console.warn('[API] Push token registration failed:', error);
    }
  },

  // DAILY SUMMARY
  getDailySummary: async (asset?: string): Promise<Record<string, unknown>> => {
    try {
      const params = asset ? `?asset=${asset}` : '';
      const res = await api.get(`/api/mobile/daily-summary${params}`);
      return res.data;
    } catch (error) {
      return { asset: asset || 'BTC', signalsToday: 0 };
    }
  },

  unregisterPushToken: async (pushToken: string): Promise<void> => {
    try {
      await api.delete('/api/mobile/push/unregister', { data: { pushToken } });
    } catch (error) {
      // Silent fail
    }
  },

  getPushStatus: async (): Promise<PushStatus> => {
    try {
      const res = await api.get('/api/mobile/push/status');
      return res.data;
    } catch (error) {
      return { hasToken: false, tokenCount: 0, sentToday: 0, pendingCount: 0, recentNotifications: [] };
    }
  },

  trackPushOpened: async (notificationId: string, data: Record<string, unknown>): Promise<void> => {
    try {
      await api.post('/api/mobile/push/opened', { notificationId, data });
    } catch (error) {
      // Silent fail
    }
  },

  // PUSH INTELLIGENCE
  checkPushTriggers: async (): Promise<any> => {
    try {
      const res = await api.post('/api/mobile/push/check-triggers');
      return res.data;
    } catch (error) {
      return { ok: false };
    }
  },

  sendPush: async (type: string, symbol: string, pnl?: number, message?: string): Promise<any> => {
    try {
      const res = await api.post('/api/mobile/push/send', { type, symbol, pnl, message });
      return res.data;
    } catch (error) {
      return { ok: false };
    }
  },

  // EDGE TRACKING
  trackEdge: async (edgeId: string, symbol: string, action: 'track' | 'untrack' | 'convert' = 'track'): Promise<any> => {
    try {
      const res = await api.post('/api/mobile/edge/track', { edgeId, symbol, action });
      return res.data;
    } catch (error) {
      return { ok: false };
    }
  },

  getTrackedEdges: async (): Promise<any> => {
    try {
      const res = await api.get('/api/mobile/edge/tracked');
      return res.data;
    } catch (error) {
      return { ok: false, tracked: [] };
    }
  },

  // TRADING
  getTradingBootstrap: async (): Promise<TradingBootstrap> => {
    try {
      const res = await api.get('/api/mobile/trading/bootstrap');
      return res.data;
    } catch (error) {
      return {
        status: 'SUN',
        hasAccess: true,
        modules: { markets: true, trade: false, positions: false },
        message: 'Trading system is under development',
      };
    }
  },

  // ACCOUNT MANAGEMENT — 2-step email change with OTP
  requestEmailChange: async (email: string): Promise<{ success: boolean; step?: string; deliveryMethod?: string; devCode?: string; message?: string }> => {
    try {
      const res = await api.patch('/api/mobile/auth/update-email', { email });
      return res.data;
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to request email change';
      return { success: false, message: detail };
    }
  },

  confirmEmailChange: async (code: string): Promise<{ success: boolean; user?: Record<string, unknown>; message?: string }> => {
    try {
      const res = await api.post('/api/mobile/auth/confirm-email-change', { code });
      return res.data;
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to confirm email change';
      return { success: false, message: detail };
    }
  },

  uploadAvatar: async (avatarBase64: string): Promise<{ success: boolean; user?: Record<string, unknown>; message?: string }> => {
    try {
      const res = await api.post('/api/mobile/profile/avatar', { avatar: avatarBase64 });
      return res.data;
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to upload avatar';
      return { success: false, message: detail };
    }
  },

  setPassword: async (password: string, totpCode: string): Promise<{ success: boolean; message?: string }> => {
    try {
      const res = await api.post('/api/mobile/auth/set-password', { password, totpCode });
      return res.data;
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to set password';
      return { success: false, message: detail };
    }
  },

  changePassword: async (currentPassword: string, newPassword: string, totpCode: string): Promise<{ success: boolean; message?: string }> => {
    try {
      const res = await api.post('/api/mobile/auth/change-password', { currentPassword, newPassword, totpCode });
      return res.data;
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to change password';
      return { success: false, message: detail };
    }
  },

  // REFERRALS
  getReferrals: async (): Promise<ReferralData> => {
    try {
      const res = await api.get('/api/mobile/auth/referrals');
      return res.data;
    } catch (error) {
      return { code: '', invites: 0, paidReferrals: 0, earned: '$0', shareUrl: '' };
    }
  },

  // GROWTH OS
  getGrowthProfile: async (): Promise<GrowthProfile | null> => {
    try {
      const res = await api.get('/api/growth/me');
      return res.data;
    } catch {
      return null;
    }
  },

  getLeaderboard: async (season?: string): Promise<LeaderboardEntry[]> => {
    try {
      const url = season ? `/api/growth/leaderboard?season=${season}` : '/api/growth/leaderboard';
      const res = await api.get(url);
      return res.data?.entries || [];
    } catch {
      return [];
    }
  },

  applyGrowthCode: async (code: string): Promise<{ ok: boolean; message?: string; error?: string }> => {
    try {
      const res = await api.post('/api/growth/apply', { code });
      return res.data;
    } catch (e: any) {
      return { ok: false, error: e?.response?.data?.detail || 'Failed to apply code' };
    }
  },

  getShareCard: async (asset: string, pnl: number): Promise<ShareCard | null> => {
    try {
      const res = await api.get(`/api/growth/share?asset=${asset}&pnl=${pnl}`);
      return res.data;
    } catch {
      return null;
    }
  },

  applyReferralCode: async (code: string): Promise<{ success: boolean; message?: string }> => {
    try {
      const res = await api.post('/api/mobile/auth/referrals/apply', { code });
      return res.data;
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to apply code';
      return { success: false, message: detail };
    }
  },

  // 2FA
  setup2FA: async (): Promise<{ secret: string; uri: string; issuer: string; account: string }> => {
    const res = await api.post('/api/mobile/auth/2fa/setup');
    return res.data;
  },

  verify2FA: async (code: string): Promise<{ success: boolean; message?: string }> => {
    try {
      const res = await api.post('/api/mobile/auth/2fa/verify', { code });
      return res.data;
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Verification failed';
      return { success: false, message: detail };
    }
  },

  disable2FA: async (code: string): Promise<{ success: boolean; message?: string }> => {
    try {
      const res = await api.post('/api/mobile/auth/2fa/disable', { code });
      return res.data;
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to disable 2FA';
      return { success: false, message: detail };
    }
  },

  // TELEGRAM LINKING (via bot)
  getTelegramLinkCode: async (): Promise<{ success: boolean; code?: string; botUrl?: string }> => {
    try {
      const res = await api.post('/api/mobile/auth/telegram-link-code');
      return res.data;
    } catch (error: any) {
      return { success: false };
    }
  },

  getTelegramStatus: async (): Promise<{ linked: boolean; username?: string; chatId?: number }> => {
    try {
      const res = await api.get('/api/mobile/auth/telegram-status');
      return res.data;
    } catch {
      return { linked: false };
    }
  },

  unlinkTelegram: async (): Promise<{ success: boolean }> => {
    try {
      const res = await api.delete('/api/mobile/auth/unlink-telegram');
      return res.data;
    } catch (error: any) {
      return { success: false };
    }
  },

  // ═══ PREDICTION CHART ═══
  getPredictionChart: async (symbol: string = 'BTC', horizon: string = '30D') => {
    const res = await api.get(`/api/mobile/prediction-chart?symbol=${symbol}&horizon=${horizon}`);
    return res.data;
  },
};
