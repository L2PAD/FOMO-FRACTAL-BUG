/**
 * OnChain Context API for Prediction Page
 */

const API_URL = process.env.REACT_APP_BACKEND_URL || "";

export interface OnchainChartDataPoint {
  t: number;
  score: number;
  confidence: number;
  exchangePressure: number;
  flowScore: number;
  whaleActivity: number;
  networkHeat: number;
  state: 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL' | 'LOW_CONF' | 'NO_DATA';
}

export interface OnchainChartLatest {
  t: number;
  score: number;
  confidence: number;
  state: 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL' | 'LOW_CONF' | 'NO_DATA';
  drivers: string[];
  flags: string[];
}

export interface OnchainChartResponse {
  ok: boolean;
  symbol: string;
  window: string;
  policy: {
    id: string;
    version: string;
    name: string;
  } | null;
  series: OnchainChartDataPoint[];
  latest: OnchainChartLatest | null;
  provider: string;
  generatedAt: number;
}

export async function getOnchainChart(
  symbol: string,
  window = '30d'
): Promise<OnchainChartResponse> {
  const res = await fetch(
    `${API_URL}/api/v10/onchain-v2/chart/${symbol}?window=${window}`,
    { cache: 'no-store' }
  );
  
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  
  return res.json();
}

export async function getOnchainContext(symbol: string) {
  const res = await fetch(
    `${API_URL}/api/v10/onchain-v2/context/${symbol}`,
    { cache: 'no-store' }
  );
  
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  
  return res.json();
}
