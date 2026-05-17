/**
 * OnChain V2 — AltFlow Confidence Calculator
 * ============================================
 * 
 * STEP 3: Unified confidence calculation for AltFlow signals
 * 
 * Factors:
 * - Price source quality (CHAINLINK > TWAP > DEX_VWAP > NONE)
 * - Pool status and score
 * - Evidence (trades, span, priced share)
 * - Flow stability (anti-spike)
 */

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type PriceSource = 'CHAINLINK' | 'TWAP' | 'DEX_VWAP' | 'NONE';
export type PoolStatus = 'ACTIVE' | 'DEGRADED' | 'DISABLED' | 'UNKNOWN';
export type FlagSeverity = 'INFO' | 'WARN' | 'CRITICAL';

export interface AltflowFlag {
  code: string;
  severity: FlagSeverity;
  detail?: string;
}

export interface ConfidenceInput {
  priceSource: PriceSource;
  priceConfidence?: number | null;
  poolStatus: PoolStatus;
  poolScore: number;           // 0..100
  trades: number;
  spanHours: number;
  pricedShare: number;         // 0..1
  dexNetUsd: number;
  cexNetUsd: number;
  whaleNetUsd: number;
}

export interface ConfidenceResult {
  confidence: number;          // 0..1
  flags: AltflowFlag[];
  breakdown: {
    price: number;
    pool: number;
    trades: number;
    span: number;
    priced: number;
    stability: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

function weightPrice(src: PriceSource): number {
  switch (src) {
    case 'CHAINLINK': return 1.0;
    case 'TWAP': return 0.8;
    case 'DEX_VWAP': return 0.55;
    default: return 0.10;
  }
}

function weightPoolStatus(s: PoolStatus): number {
  switch (s) {
    case 'ACTIVE': return 1.0;
    case 'DEGRADED': return 0.7;
    case 'DISABLED': return 0.3;
    default: return 0.3;
  }
}

function weightTrades(trades: number): number {
  if (trades < 10) return 0.35;
  if (trades < 30) return 0.60;
  if (trades < 80) return 0.80;
  return 1.0;
}

function weightSpanHours(span: number): number {
  if (span < 6) return 0.5;
  if (span < 24) return 0.8;
  return 1.0;
}

function weightPricedShare(ps: number): number {
  if (ps < 0.4) return 0.55;
  if (ps < 0.7) return 0.75;
  return 1.0;
}

function dominancePenalty(dexUsd: number, cexUsd: number, whaleUsd: number): number {
  const a = Math.abs(dexUsd);
  const b = Math.abs(cexUsd);
  const c = Math.abs(whaleUsd);
  const sum = a + b + c + 1e-9;
  const dom = Math.max(a, b, c) / sum;
  return dom > 0.85 ? 0.75 : 1.0;
}

// ═══════════════════════════════════════════════════════════════
// MAIN FUNCTION
// ═══════════════════════════════════════════════════════════════

export function computeAltflowConfidence(args: ConfidenceInput): ConfidenceResult {
  const flags: AltflowFlag[] = [];

  // Base ceiling (multiplied by factors)
  const base = 0.85;

  // Price factor
  const priceWeight = weightPrice(args.priceSource);
  if (args.priceSource === 'NONE') {
    flags.push({ code: 'NO_PRICE', severity: 'WARN' });
  }

  // Pool factor
  const poolWeight = weightPoolStatus(args.poolStatus) * clamp01(args.poolScore / 100);
  if (args.poolStatus !== 'ACTIVE' && args.poolStatus !== 'UNKNOWN') {
    flags.push({ code: `POOL_${args.poolStatus}`, severity: 'INFO' });
  }

  // Trades factor
  const tradesWeight = weightTrades(args.trades);
  if (args.trades < 10) {
    flags.push({ 
      code: 'LOW_TRADES', 
      severity: 'WARN', 
      detail: `trades=${args.trades}`,
    });
  }

  // Span factor
  const spanWeight = weightSpanHours(args.spanHours);
  if (args.spanHours < 6) {
    flags.push({ 
      code: 'SHORT_WINDOW', 
      severity: 'INFO', 
      detail: `spanHours=${args.spanHours.toFixed(1)}`,
    });
  }

  // Priced share factor
  const pricedWeight = weightPricedShare(args.pricedShare);
  if (args.pricedShare < 0.7) {
    flags.push({ 
      code: 'LOW_PRICED_SHARE', 
      severity: 'INFO', 
      detail: `pricedShare=${Math.round(args.pricedShare * 100)}%`,
    });
  }

  // Stability factor (anti-spike)
  const stability = dominancePenalty(args.dexNetUsd, args.cexNetUsd, args.whaleNetUsd);
  if (stability < 1) {
    flags.push({ code: 'ONE_SIDED_FLOW', severity: 'INFO' });
  }

  // Use provided price confidence if available
  const pConf = args.priceConfidence != null ? clamp01(args.priceConfidence) : priceWeight;

  // Final confidence
  const confidence = clamp01(
    base * pConf * poolWeight * tradesWeight * spanWeight * pricedWeight * stability
  );

  return {
    confidence,
    flags,
    breakdown: {
      price: pConf,
      pool: poolWeight,
      trades: tradesWeight,
      span: spanWeight,
      priced: pricedWeight,
      stability,
    },
  };
}

console.log('[OnChain V2] AltFlow Confidence Calculator loaded');
