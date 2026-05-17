/**
 * META BRAIN V2 — MARKET REGIME PROVIDER
 * ========================================
 *
 * Detects current market regime from macro-intel.
 * Maps 8 granular MarketRegimes → 4 MetaRegimes:
 *
 *   TREND:      BTC_FLIGHT_TO_SAFETY, BTC_LEADS_ALT_FOLLOW, ALT_SEASON
 *   RANGE:      ALT_ROTATION
 *   RISK_OFF:   PANIC_SELL_OFF, BTC_MAX_PRESSURE, FULL_RISK_OFF, CAPITAL_EXIT
 *   TRANSITION: fallback / unknown
 *
 * Source: GET http://127.0.0.1:8003/api/v10/macro-intel/regime
 */

import { MetaRegime, DEFAULT_REGIME } from '../weights/regime_weights.js';

const API_BASE = 'http://127.0.0.1:8003';

/** Mapping: granular → meta regime */
const REGIME_MAP: Record<string, MetaRegime> = {
  BTC_FLIGHT_TO_SAFETY: 'TREND',
  BTC_LEADS_ALT_FOLLOW: 'TREND',
  ALT_SEASON:           'TREND',
  ALT_ROTATION:         'RANGE',
  PANIC_SELL_OFF:       'RISK_OFF',
  BTC_MAX_PRESSURE:     'RISK_OFF',
  FULL_RISK_OFF:        'RISK_OFF',
  CAPITAL_EXIT:         'RISK_OFF',
};

export interface RegimeResult {
  metaRegime: MetaRegime;
  sourceRegime: string | null;
  source: 'macro-intel' | 'fallback';
  riskLevel: string | null;
  confidenceMultiplier: number | null;
}

/**
 * Get current market regime.
 * Falls back to TRANSITION if API unreachable or unknown regime.
 */
export async function getMarketRegime(asset: string): Promise<RegimeResult> {
  try {
    const resp = await fetch(`${API_BASE}/api/v10/macro-intel/regime`, {
      signal: AbortSignal.timeout(3000),
    });
    const data = await resp.json() as any;

    if (!data.ok || !data.data?.regime) {
      return fallback('API returned not-ok');
    }

    const sourceRegime = data.data.regime as string;
    const metaRegime = REGIME_MAP[sourceRegime] ?? DEFAULT_REGIME;

    return {
      metaRegime,
      sourceRegime,
      source: 'macro-intel',
      riskLevel: data.data.riskLevel ?? null,
      confidenceMultiplier: data.data.confidenceMultiplier ?? null,
    };
  } catch {
    return fallback('macro-intel unreachable');
  }
}

function fallback(_reason: string): RegimeResult {
  return {
    metaRegime: DEFAULT_REGIME,
    sourceRegime: null,
    source: 'fallback',
    riskLevel: null,
    confidenceMultiplier: null,
  };
}
