/**
 * mbrain-api — thin client for the side-car observability endpoints.
 * Used by HomeScreen / SignalsScreen / TradeScreen / PortfolioScreen.
 * READ-ONLY. NO ORDERS. NO EXECUTION.
 */
import Constants from 'expo-constants';

const API_URL =
  (Constants.expoConfig?.extra as any)?.apiUrl ||
  process.env.EXPO_PUBLIC_BACKEND_URL ||
  '';

async function jget<T>(path: string): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(`${API_URL}${path}`, { signal: ctrl.signal });
    return (await res.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

async function jpost<T>(path: string, body?: any): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    return (await res.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

export const mbrainApi = {
  // — Verdicts —
  listVerdicts: (limit = 50) =>
    jget<{ ok: boolean; cards: any[]; error?: string }>(
      `/api/mbrain/verdicts/list?limit=${limit}`,
    ),
  sweepVerdicts: (
    assets = 'BTC,ETH,SOL,BNB,XRP,DOGE',
    horizons = '1D,7D,30D',
    range = '7d',
  ) =>
    jget<{ ok: boolean; cards: any[] }>(
      `/api/mbrain/verdicts/sweep?assets=${assets}&horizons=${horizons}&range=${range}`,
    ),

  // — Parallel portfolios —
  parallelPortfolios: (limit = 400, includeResolved = true) =>
    jget<any>(
      `/api/mbrain/positions/parallel?limit=${limit}&include_resolved=${includeResolved}`,
    ),

  // — Attribution —
  paperAttribution: (limit = 500, includeResolved = true) =>
    jget<any>(
      `/api/mbrain/positions/attribution?include_resolved=${includeResolved}&limit=${limit}`,
    ),
  realizedAttribution: (limit = 2000) =>
    jget<any>(`/api/mbrain/attribution/realized?limit=${limit}`),

  // — M2B resolve trigger (no live exec) —
  resolveAsymmetry: () =>
    jpost<any>(`/api/mbrain/integrity/asymmetry/resolve?only_ready=true`),

  // — Stage A-6 · Outcome Memory (Cognitive Accountability) —
  outcomesHealth: () =>
    jget<{
      ok: boolean;
      pending?: number;
      resolved?: number;
      expired?: number;
      totalOutcomes?: number;
      totalDecisions?: number;
      coveragePct?: number;
      maturePending?: number;
      classifications?: Record<string, number>;
      asOf?: string;
      reason?: string;
    }>(`/api/mbrain/outcomes/health`),
  outcomesRecent: (limit = 25) =>
    jget<{ ok: boolean; count: number; items: any[]; asOf?: string }>(
      `/api/mbrain/outcomes/recent?limit=${limit}`,
    ),

  // — Stage A-7 · Shadow Verdict Runtime (Shadow Forward Structure) —
  shadowHealth: () =>
    jget<{
      ok: boolean;
      symbols?: number;
      totalVerdicts?: number;
      blocked?: number;
      wait?: number;
      considered?: number;
      unresolved?: number;
      lastSweepAt?: string | null;
      dedupWindowMin?: number;
      asOf?: string;
      reason?: string;
    }>(`/api/mbrain/shadow-runtime/health`),
  shadowSummary: (symbols?: string) =>
    jget<{
      ok: boolean;
      totalVerdicts?: number;
      perSymbol?: Record<string, any>;
      distribution?: Record<string, number>;
      topReasons?: [string, number][];
      topBlockedBy?: [string, number][];
      dedupWindowMin?: number;
      asOf?: string;
    }>(`/api/mbrain/shadow-runtime/summary${symbols ? `?symbols=${symbols}` : ''}`),
  shadowRecent: (limit = 25, symbol?: string) => {
    const qs: string[] = [`limit=${limit}`];
    if (symbol) qs.push(`symbol=${symbol}`);
    return jget<{ ok: boolean; count: number; items: any[]; asOf?: string }>(
      `/api/mbrain/shadow-runtime/recent?${qs.join('&')}`,
    );
  },

  // — Phase B · Operator Cognition Observatory —
  observatoryState: () =>
    jget<{
      ok: boolean;
      reason?: string;
      phrase?: string;
      asOf?: string;
      universe?: string[];
      deploymentClimate?: any;
      alignmentDrift?: any;
      cognitiveMemory?: any;
      shadowStructures?: any;
      regimeContinuity?: any;
    }>(`/api/mbrain/observatory/state`),
};

export const MBRAIN_API_URL = API_URL;
