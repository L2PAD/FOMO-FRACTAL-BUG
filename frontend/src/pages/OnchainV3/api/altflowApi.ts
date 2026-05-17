/**
 * On-chain v3 — AltFlow API Extension
 * ====================================
 * 
 * PHASE 3: Signal Center API
 * STEP 3: Enhanced with quality, evidence, flags
 */

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// =====================
// Types
// =====================

export type PriceSource = 'CHAINLINK' | 'TWAP' | 'DEX_VWAP' | 'NONE';
export type PoolStatus = 'ACTIVE' | 'DEGRADED' | 'DISABLED' | 'UNKNOWN';
export type FlagSeverity = 'INFO' | 'WARN' | 'CRITICAL';

export interface AltFlowFlag {
  code: string;
  severity: FlagSeverity;
  detail?: string;
}

export interface AltFlowQuality {
  priceSource: PriceSource;
  priceConfidence: number | null;
  poolStatus: PoolStatus;
  poolScore: number;
}

export interface AltFlowEvidence {
  trades: number;
  uniquePools: number;
  spanHours: number;
  pricedShare: number;
}

export interface AltFlowItem {
  symbol: string;
  address?: string;
  chainId?: number;
  score: number;
  side: 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL';
  confidence: number;
  // STEP 3: Enhanced fields
  quality?: AltFlowQuality;
  evidence?: AltFlowEvidence;
  components: {
    cexNetUsd: number;
    dexNetUsd: number;
    whaleUsd: number;
  };
  drivers: string[];
  flags: (string | AltFlowFlag)[];
  totalUsd?: number;
  buyUsd?: number;
  sellUsd?: number;
  updatedAt?: number;
}

export interface AltFlowResponse {
  ok: boolean;
  window: string;
  updatedAt: number;
  isDemo?: boolean;
  meta: {
    tokenCount: number;
    labelsCoverage: number;
    confidence: number;
    jobRunning?: boolean;
    lastTick?: number;
  };
  items: AltFlowItem[];
  topAccumulation: AltFlowItem[];
  topDistribution: AltFlowItem[];
}

export interface AltFlowJobStatus {
  ok: boolean;
  job: {
    enabled: boolean;
    intervalMs: number;
    running: boolean;
    tickCount: number;
    lastTickAt: number;
    lastError: string | null;
    lastResult: {
      window24h: { tokens: number; topAcc: string | null; topDist: string | null };
      window7d: { tokens: number; topAcc: string | null; topDist: string | null };
    };
  };
}

// =====================
// Demo Data (used when API returns empty)
// =====================

const DEMO_TOKENS: AltFlowItem[] = [
  {
    symbol: 'ETH',
    address: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
    score: 0.72,
    side: 'ACCUMULATION',
    confidence: 0.68,
    components: { cexNetUsd: -128_000_000, dexNetUsd: 45_000_000, whaleUsd: 76_000_000 },
    drivers: ['CEX outflows detected', 'DEX buy pressure rising'],
    flags: [],
  },
  {
    symbol: 'SOL',
    address: '0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0',
    score: 0.45,
    side: 'ACCUMULATION',
    confidence: 0.54,
    components: { cexNetUsd: -42_000_000, dexNetUsd: 18_000_000, whaleUsd: 12_000_000 },
    drivers: ['Moderate CEX outflows'],
    flags: ['LOW_CONFIDENCE'],
  },
  {
    symbol: 'LINK',
    address: '0x514910771af9ca656af840dff83e8264ecf986ca',
    score: 0.38,
    side: 'ACCUMULATION',
    confidence: 0.52,
    components: { cexNetUsd: -15_000_000, dexNetUsd: 8_000_000, whaleUsd: 5_000_000 },
    drivers: ['Slight CEX outflows'],
    flags: [],
  },
  {
    symbol: 'ARB',
    address: '0xb50721bcf8d664c30412cfbc6cf7a15145234ad1',
    score: 0.22,
    side: 'NEUTRAL',
    confidence: 0.48,
    components: { cexNetUsd: -5_000_000, dexNetUsd: 3_000_000, whaleUsd: 2_000_000 },
    drivers: ['Flow balanced'],
    flags: ['LOW_CONFIDENCE'],
  },
  {
    symbol: 'OP',
    address: '0x4200000000000000000000000000000000000042',
    score: 0.15,
    side: 'NEUTRAL',
    confidence: 0.45,
    components: { cexNetUsd: 2_000_000, dexNetUsd: -1_000_000, whaleUsd: 500_000 },
    drivers: ['Slight CEX inflows'],
    flags: ['LOW_CONFIDENCE'],
  },
  {
    symbol: 'AVAX',
    address: '0xd77d7e72856d7c90c30f74ab95e5b9f41c7c8000',
    score: -0.28,
    side: 'DISTRIBUTION',
    confidence: 0.58,
    components: { cexNetUsd: 45_000_000, dexNetUsd: -18_000_000, whaleUsd: 8_000_000 },
    drivers: ['CEX inflows rising', 'DEX sell pressure'],
    flags: [],
  },
  {
    symbol: 'MATIC',
    address: '0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0',
    score: -0.42,
    side: 'DISTRIBUTION',
    confidence: 0.62,
    components: { cexNetUsd: 78_000_000, dexNetUsd: -32_000_000, whaleUsd: 15_000_000 },
    drivers: ['Strong CEX inflows', 'DEX sell pressure'],
    flags: [],
  },
  {
    symbol: 'DOGE',
    address: '0x4206931337dc273a630d328da6441786bfad668f',
    score: -0.55,
    side: 'DISTRIBUTION',
    confidence: 0.65,
    components: { cexNetUsd: 120_000_000, dexNetUsd: -45_000_000, whaleUsd: 25_000_000 },
    drivers: ['Heavy CEX inflows', 'Strong DEX sell pressure', 'Whale selling'],
    flags: [],
  },
  {
    symbol: 'PEPE',
    address: '0x6982508145454ce325ddbe47a25d4ec3d2311933',
    score: -0.68,
    side: 'DISTRIBUTION',
    confidence: 0.72,
    components: { cexNetUsd: 180_000_000, dexNetUsd: -85_000_000, whaleUsd: 42_000_000 },
    drivers: ['Extreme CEX inflows', 'Heavy DEX dumping', 'Whale exit'],
    flags: [],
  },
  {
    symbol: 'SHIB',
    address: '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
    score: -0.75,
    side: 'DISTRIBUTION',
    confidence: 0.78,
    components: { cexNetUsd: 220_000_000, dexNetUsd: -110_000_000, whaleUsd: 65_000_000 },
    drivers: ['Massive CEX inflows', 'Heavy DEX dumping', 'Large whale exits'],
    flags: [],
  },
];

function getDemoData(window: string): AltFlowResponse {
  const now = Date.now();
  const items = DEMO_TOKENS.map((t, i) => ({
    ...t,
    updatedAt: now - i * 60000, // Stagger updates
  }));
  
  const sorted = [...items].sort((a, b) => b.score - a.score);
  const accum = sorted.filter(t => t.score > 0.2).slice(0, 5);
  const distrib = sorted.filter(t => t.score < -0.2).slice(-5).reverse();
  
  return {
    ok: true,
    window,
    updatedAt: now,
    isDemo: true, // Flag for UI to show demo indicator
    meta: {
      tokenCount: items.length,
      labelsCoverage: 0.85,
      confidence: 0.65,
      jobRunning: true,
      lastTick: now - 300000,
    },
    items,
    topAccumulation: accum,
    topDistribution: distrib,
  };
}

// =====================
// API Functions
// =====================

/**
 * Fetch alt flow rankings
 * P0.7: Added optional entityId filter for entity overlay
 */
export async function fetchAltFlow(window: '24h' | '7d' = '24h', entityId?: string, chainId: number = 1): Promise<AltFlowResponse> {
  try {
    let url = `${API_BASE}/api/v10/onchain-v2/market/altflow?window=${window}&chainId=${chainId}`;
    if (entityId) {
      url += `&entityId=${encodeURIComponent(entityId)}`;
    }
    
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    
    const data = await res.json();
    
    // Check if we have real data
    if (data.ok && data.totalTokens > 0) {
      // Map API item to our format
      const mapItem = (t: any): AltFlowItem => ({
        symbol: t.symbol,
        address: t.address,
        chainId: t.chainId,
        score: t.score || 0,
        side: t.side || (t.score > 60 ? 'ACCUMULATION' : t.score < 40 ? 'DISTRIBUTION' : 'NEUTRAL'),
        confidence: t.confidence || 0,
        // STEP 3: Enhanced fields
        quality: t.quality || undefined,
        evidence: t.evidence || undefined,
        components: t.components || {
          cexNetUsd: 0,
          dexNetUsd: t.dexNetUsd || 0,
          whaleUsd: 0,
        },
        drivers: t.drivers || [],
        flags: t.flags || [],
        totalUsd: t.totalUsd,
        buyUsd: t.buyUsd,
        sellUsd: t.sellUsd,
        updatedAt: data.generatedAt,
      });
      
      const items = [
        ...(data.topAccumulation || []).map(mapItem), 
        ...(data.topDistribution || []).map(mapItem),
      ];
      
      return {
        ok: true,
        window: data.window,
        updatedAt: data.generatedAt,
        meta: {
          tokenCount: data.totalTokens,
          labelsCoverage: items.filter(i => i.symbol && i.symbol !== 'UNKNOWN').length / Math.max(items.length, 1),
          confidence: items.reduce((sum, i) => sum + i.confidence, 0) / Math.max(items.length, 1),
        },
        items,
        topAccumulation: (data.topAccumulation || []).map(mapItem),
        topDistribution: (data.topDistribution || []).map(mapItem),
      };
    }
    
    // Return demo data when API is empty
    console.log('[AltFlow] API returned empty, using demo data');
    return getDemoData(window);
    
  } catch (error) {
    console.error('[AltFlow] Fetch error, using demo data:', error);
    return getDemoData(window);
  }
}

/**
 * Fetch alt flow job status
 */
export async function fetchAltFlowJobStatus(): Promise<AltFlowJobStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/altflow/job/status`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/**
 * Force refresh alt flow data
 */
export async function refreshAltFlow(window: '24h' | '7d' = '24h', chainId: number = 1): Promise<AltFlowResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/v10/onchain-v2/market/altflow?window=${window}&chainId=${chainId}&refresh=true`);
    if (!res.ok) throw new Error(`Refresh failed: ${res.status}`);
    return fetchAltFlow(window, undefined, chainId);
  } catch (error) {
    console.error('[AltFlow] Refresh error:', error);
    return getDemoData(window);
  }
}
