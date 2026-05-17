/**
 * On-chain v3 — API Layer
 * ========================
 * 
 * Central API client for all On-chain v3 data fetching.
 * Connects to existing backend endpoints.
 */

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// Types
export interface LareV2Latest {
  ok: boolean;
  data: {
    version: string;
    window: string;
    bucketTs: number;
    computedAt: number;
    score: number;
    confidence: number;
    regime: 'NEUTRAL' | 'RISK_ON_ALTS' | 'MODERATE_RISK_ON' | 'MODERATE_RISK_OFF' | 'RISK_OFF';
    gate: {
      riskCap: number;
      allowAggressiveRisk: boolean;
      blockNewPositions: boolean;
      reason: string;
    };
    components: Array<{
      key: string;
      score: number;
      direction: -1 | 0 | 1;
      strength: number;
      confidence: number;
      drivers: string[];
      flags: string[] | Array<{ code: string; severity: string; message: string }>;
      raw: { bucketTs: number | null };
    }>;
    drivers: string[];
    flags: string[];
  };
}

export interface LiquiditySeries {
  ok: boolean;
  key: string;
  window: string;
  count: number;
  series: Array<{
    t: number;
    score: number;
    confidence: number;
    regime: string;
    flags: string[];
    drivers: string[];
  }>;
}

export interface StablesAggregate {
  ok: boolean;
  aggregate: {
    window: string;
    bucketTs: number;
    computedAt: number;
    chainsCovered: number;
    metrics: {
      mintCount: number;
      burnCount: number;
      mintAmount: number;
      burnAmount: number;
      netAmount: number;
      mintUsd: number;
      burnUsd: number;
      netUsd: number;
    };
    byToken: Record<string, {
      mintCount: number;
      burnCount: number;
      mintAmount: number;
      burnAmount: number;
      netAmount: number;
    }>;
    score: {
      value: number;
      regime: string;
      confidence: number;
    };
    drivers: string[];
    flags: string[];
  };
}

export interface BridgeAggregate {
  ok: boolean;
  window: string;
  bucketTs: number;
  computedAt: number;
  metrics: {
    inCount: number;
    outCount: number;
    netCount: number;
    inUsd: number;
    outUsd: number;
    netUsd: number;
    stableInUsd: number;
    stableOutUsd: number;
    stableNetUsd: number;
    whaleInUsd: number;
    whaleOutUsd: number;
    whaleNetUsd: number;
  };
  score: {
    value: number;
    regime: string;
    confidence: number;
  };
  drivers: string[];
  flags: string[];
}

export interface MarketSeries {
  ok: boolean;
  key: string;
  window: string;
  count: number;
  series: Array<{
    t: number;
    value: number;
  }>;
}

export interface AltFlowRanking {
  ok: boolean;
  window: string;
  generatedAt: number;
  topAccumulation: Array<{
    symbol: string;
    score: number;
    delta: number;
  }>;
  topDistribution: Array<{
    symbol: string;
    score: number;
    delta: number;
  }>;
  totalTokens: number;
}

// API Functions

/**
 * Fetch LARE v2 latest composite score
 */
export async function fetchLareV2Latest(window: '24h' | '7d' = '24h', chainId: number = 1): Promise<LareV2Latest> {
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/lare-v2/latest?window=${window}&chainId=${chainId}`);
  if (!res.ok) throw new Error(`Failed to fetch LARE v2 latest: ${res.status}`);
  return res.json();
}

/**
 * Fetch liquidity score series for charting
 */
export async function fetchLiquiditySeries(window: '24h' | '7d' | '30d' = '24h', chainId: number = 1): Promise<LiquiditySeries> {
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/liquidity/series?window=${window}&chainId=${chainId}`);
  if (!res.ok) throw new Error(`Failed to fetch liquidity series: ${res.status}`);
  return res.json();
}

/**
 * Fetch stablecoin aggregate data
 */
export async function fetchStablesAggregate(window: '24h' | '7d' | '30d' = '24h', chainId: number = 1): Promise<StablesAggregate> {
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/stables/aggregate/latest?window=${window}&chainId=${chainId}`);
  if (!res.ok) throw new Error(`Failed to fetch stables aggregate: ${res.status}`);
  return res.json();
}

/**
 * Fetch bridge aggregate data
 */
export async function fetchBridgeAggregate(window: '24h' | '7d' = '24h', chainId: number = 1): Promise<BridgeAggregate> {
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/bridge/aggregate/latest?window=${window}&chainId=${chainId}`);
  if (!res.ok) throw new Error(`Failed to fetch bridge aggregate: ${res.status}`);
  return res.json();
}

/**
 * Fetch market series data (PURE_ALT_CAP, STABLE_SUPPLY_TOTAL, etc.)
 */
export async function fetchMarketSeries(key: string, window: '24h' | '7d' | '30d' = '24h', chainId: number = 1): Promise<MarketSeries> {
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/series?key=${key}&window=${window}&chainId=${chainId}`);
  if (!res.ok) throw new Error(`Failed to fetch market series: ${res.status}`);
  return res.json();
}

/**
 * Fetch alt flow ranking
 */
export async function fetchAltFlowRanking(window: '24h' | '7d' = '24h', chainId: number = 1): Promise<AltFlowRanking> {
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/altflow?window=${window}&chainId=${chainId}`);
  if (!res.ok) throw new Error(`Failed to fetch alt flow ranking: ${res.status}`);
  return res.json();
}

/**
 * Format USD value with sign
 */
export function formatUsd(n: number): string {
  const abs = Math.abs(n);
  const sign = n >= 0 ? '+' : '-';
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(0)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

/**
 * Format percentage with sign
 */
export function formatPct(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;
}

/**
 * Map regime to UI colors
 */
export function getRegimeColors(regime: string) {
  const colors: Record<string, { bg: string; text: string }> = {
    RISK_ON_ALTS: { bg: 'bg-green-500/20', text: 'text-green-400' },
    MODERATE_RISK_ON: { bg: 'bg-emerald-500/20', text: 'text-emerald-400' },
    NEUTRAL: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
    MODERATE_RISK_OFF: { bg: 'bg-amber-500/20', text: 'text-amber-400' },
    RISK_OFF: { bg: 'bg-red-500/20', text: 'text-red-400' },
  };
  return colors[regime] || colors.NEUTRAL;
}

/**
 * Calculate score color based on value (0-100 scale, 50 = neutral)
 */
export function getScoreColor(score: number): string {
  if (score >= 65) return 'text-green-400';
  if (score >= 55) return 'text-emerald-400';
  if (score >= 45) return 'text-blue-400';
  if (score >= 35) return 'text-amber-400';
  return 'text-red-400';
}

/**
 * Calculate confidence color
 */
export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.6) return 'text-green-400';
  if (confidence >= 0.4) return 'text-amber-400';
  return 'text-red-400';
}

// ═══════════════════════════════════════════════════════════════
// PHASE 4: Assets API
// ═══════════════════════════════════════════════════════════════

export interface AssetProfile {
  ok: boolean;
  token?: {
    chainId: number;
    symbol: string;
    name: string | null;
    address: string;
    decimals: number;
  };
  snapshot?: {
    priceUsd: number | null;
    priceSource: string;
    reliability: number;
  };
  flow?: {
    window: string;
    latest: {
      ts: string;
      dexNetUsd: number;
      cexNetUsd: number;
      whaleNetUsd: number;
      trades: number;
      pricedShare: number;
    } | null;
    history: Array<{
      ts: string;
      dexNetUsd: number;
      cexNetUsd: number;
      whaleNetUsd: number;
      trades: number;
    }>;
  };
  pools?: {
    activeCount: number;
    degradedCount: number;
    avgScore: number;
    totalTvlUsd: number;
    concentrationTop1: number;
    concentrationTop3: number;
    topPools: Array<{
      address: string;
      fee: number;
      status: string;
      score: number;
      tvlUsd: number | null;
      token0Symbol: string | null;
      token1Symbol: string | null;
    }>;
  };
  liquidityRisk?: {
    score: number;
    label: string;
    factors: {
      tvlRisk: number;
      poolRisk: number;
      concRisk: number;
    };
  };
  dataQuality?: {
    pricing: {
      usd: number | null;
      source: string;
      reliability: number;
      updatedAt: number | null;
    };
    pools: {
      scanned: number;
      active: number;
      totalTvlUsd: number;
    };
    flows: {
      hasLatest: boolean;
      latestBucketTs: string | null;
      window: string;
    };
  };
  reason?: string;
}

export interface AssetListItem {
  chainId: number;
  address: string;
  symbol: string;
  name: string | null;
  priceUsd: number | null;
  priceSource: string;
  reliability: number;
  tvlUsd?: number;
  dexNetUsd?: number;
  cexNetUsd?: number;
  whaleNetUsd?: number;
  trades?: number;
  spikeAbs?: number;
  scoreHint?: number;
  updatedAt?: string | null;
}

export interface AssetList {
  ok: boolean;
  kind: 'signals' | 'tvl' | 'spikes';
  window?: string;
  items: AssetListItem[];
  reason?: string;
}

/**
 * Fetch token intelligence profile
 */
export async function fetchAssetProfile(params: {
  chainId: number;
  token: string;
  window?: '24h' | '7d' | '30d';
}): Promise<AssetProfile> {
  const qs = new URLSearchParams({
    chainId: String(params.chainId),
    token: params.token,
    window: params.window || '7d',
  });
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/assets/profile?${qs}`);
  if (!res.ok) throw new Error(`Failed to fetch asset profile: ${res.status}`);
  return res.json();
}

/**
 * Fetch token list by criteria
 */
export async function fetchAssetList(params: {
  chainId: number;
  kind: 'signals' | 'tvl' | 'spikes';
  window?: '24h' | '7d' | '30d';
  limit?: number;
}): Promise<AssetList> {
  const qs = new URLSearchParams({
    chainId: String(params.chainId),
    kind: params.kind,
    window: params.window || '7d',
    limit: String(params.limit || 20),
  });
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/assets/list?${qs}`);
  if (!res.ok) throw new Error(`Failed to fetch asset list: ${res.status}`);
  return res.json();
}


/**
 * P0.9: Fetch structural Edge Score actor list
 */
export interface ActorScoreItem {
  entityId: string;
  entityName: string | null;
  entityType: string | null;
  attributionSource: string;
  attributionConfidence: number;
  edgeScore: number;
  coverage: number;
  activityScore: number;
  centralityScore: number;
  tokensTouched: number;
  trades: number;
  netAbsUsd: number;
}

export async function fetchActorsStructuralList(params: {
  chainId?: number;
  window?: string;
  q?: string;
  minScore?: number;
  type?: string;
  limit?: number;
}): Promise<{ ok: boolean; items: ActorScoreItem[] }> {
  const qs = new URLSearchParams({
    chainId: String(params.chainId ?? 1),
    window: params.window ?? '7d',
    q: params.q ?? '',
    minScore: String(params.minScore ?? 0),
    type: params.type ?? '',
    limit: String(params.limit ?? 80),
  });
  const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/actors/structural/list?${qs}`);
  if (!res.ok) throw new Error(`actors structural failed: ${res.status}`);
  return res.json();
}

