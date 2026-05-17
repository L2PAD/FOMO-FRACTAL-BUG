/**
 * Priority Engine
 * ===============
 * Maps signal type → base priority weight (0..100). Used by:
 *   - throttle.engine to know whether to override anti-spam (priority >= 90)
 *   - signal.selector to rank events for "Signal of the moment"
 *
 * Higher = more important. Numbers are product-calibrated, not ML.
 */

const BASE_PRIORITY: Record<string, number> = {
  LISTING: 100,
  EXPLOIT: 100,
  ETF: 95,
  POLY_MISPRICING: 95,
  METABRAIN_SHIFT: 92,
  METABRAIN_DECISION_SHIFT: 92,        // Wave 4 — "system flipped bullish/bearish"
  METABRAIN_CONVICTION_JUMP: 78,       // Wave 4 — conviction delta >= +20%
  POLY_OVERHEATED: 85,
  POLY_THESIS_WEAKENED: 82,
  REGULATION: 80,
  NEWS: 75,
  WHALE_EXCHANGE_INFLOW: 78,           // Wave 4 — $5M+ with spike
  WHALE_EXCHANGE_OUTFLOW: 78,          // Wave 4 — $5M+ with spike
  ACTOR_NARRATIVE_PUSH: 76,            // Wave 4 — high-influence narrative
  ACTOR_MENTION_SPIKE: 74,             // Wave 4 — mention burst
  POLY_REPRICING: 72,
  CONFIRMED: 70,
  PERSONAL: 70,
  MISSED: 65,
  FORMING: 40,
  TENSION: 35,
};

export function resolvePriority(event: { type?: string; meta?: any }): number {
  const t = String(event?.type || '').toUpperCase();
  const base = BASE_PRIORITY[t];
  if (typeof base === 'number') return base;

  // Fall back to meta.priority label if type unknown
  const p = String(event?.meta?.priority || '').toUpperCase();
  if (p === 'CRITICAL') return 95;
  if (p === 'HIGH') return 75;
  if (p === 'MEDIUM') return 55;
  if (p === 'LOW') return 30;
  return 50;
}

export function priorityLabel(score: number): 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' {
  if (score >= 90) return 'CRITICAL';
  if (score >= 70) return 'HIGH';
  if (score >= 45) return 'MEDIUM';
  return 'LOW';
}
