/**
 * OnChain V2 — Bridge Score Engine
 * ==================================
 * 
 * Computes BridgeScore (0..100) + regime + drivers/flags
 * from raw migration metrics.
 */

import type { BridgeAggWindow, BridgeMetrics, BridgeByBridge, BridgeScore } from './bridge_agg.model.js';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function clamp(x: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, x));
}

function tanh(x: number): number {
  const e2x = Math.exp(2 * x);
  return (e2x - 1) / (e2x + 1);
}

function formatUsd(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return `${v.toFixed(0)}`;
}

// ═══════════════════════════════════════════════════════════════
// ENGINE INPUT
// ═══════════════════════════════════════════════════════════════

export interface BridgeScoreInput {
  window: BridgeAggWindow;
  computedAt: number;
  bucketTs: number;
  
  metrics: BridgeMetrics;
  byBridge: Record<string, BridgeByBridge>;
  
  // Quality signals
  hasUsd: boolean;
  hasStable: boolean;
  hasWhale: boolean;
  eventCount: number;
}

export interface BridgeScoreOutput {
  score: BridgeScore;
  drivers: string[];
  flags: string[];
}

// ═══════════════════════════════════════════════════════════════
// SCALING CONSTANTS
// ═══════════════════════════════════════════════════════════════

const SCALE_USD_24H = 25_000_000;  // $25M for 24h normalization
const SCALE_USD_7D = 120_000_000; // $120M for 7d normalization
const SCALE_COUNT_24H = 200;
const SCALE_COUNT_7D = 800;

// ═══════════════════════════════════════════════════════════════
// MAIN ENGINE
// ═══════════════════════════════════════════════════════════════

export function computeBridgeScore(input: BridgeScoreInput): BridgeScoreOutput {
  const { window, metrics, hasUsd, hasStable, hasWhale, eventCount } = input;
  
  const flags: string[] = [];
  const drivers: string[] = [];
  
  // ─────────────────────────────────────────────────────────────
  // CONFIDENCE CALCULATION
  // ─────────────────────────────────────────────────────────────
  
  let confidence = 0.15; // Base confidence
  
  // Event count contribution
  if (eventCount >= 20) confidence += 0.10;
  if (eventCount >= 100) confidence += 0.15;
  if (eventCount >= 500) confidence += 0.10;
  
  // USD enrichment contribution
  if (!hasUsd) {
    flags.push('BRIDGE_USD_ENRICHMENT_MISSING');
  } else {
    confidence += 0.20;
  }
  
  // Classification flags contribution
  if (!hasStable) {
    flags.push('BRIDGE_STABLE_CLASSIFICATION_MISSING');
  } else {
    confidence += 0.05;
  }
  
  if (!hasWhale) {
    flags.push('BRIDGE_WHALE_CLASSIFICATION_MISSING');
  } else {
    confidence += 0.05;
  }
  
  // Low data penalty
  if (eventCount < 10) {
    flags.push('BRIDGE_LOW_DATA');
    confidence *= 0.6;
  }
  
  confidence = clamp(confidence, 0, 1);
  
  // ─────────────────────────────────────────────────────────────
  // DIRECTION SCORE (0..100)
  // ─────────────────────────────────────────────────────────────
  
  const scaleUsd = window === '24h' ? SCALE_USD_24H : SCALE_USD_7D;
  const scaleCount = window === '24h' ? SCALE_COUNT_24H : SCALE_COUNT_7D;
  
  let direction01 = 0.5; // Neutral default
  
  if (metrics.netUsd !== null) {
    // Use USD-based direction
    const x = clamp(metrics.netUsd / scaleUsd, -3, 3);
    direction01 = (tanh(x) + 1) / 2;
  } else {
    // Fallback to count-based direction
    const x = clamp(metrics.netCount / scaleCount, -3, 3);
    direction01 = (tanh(x) + 1) / 2;
    flags.push('BRIDGE_USD_FALLBACK_COUNT');
  }
  
  // Apply confidence dampening (avoid sharp moves when confidence low)
  const dampedDirection = 0.5 + (direction01 - 0.5) * clamp(confidence + 0.2, 0.2, 1);
  const scoreValue = Math.round(100 * dampedDirection);
  
  // ─────────────────────────────────────────────────────────────
  // REGIME CLASSIFICATION
  // ─────────────────────────────────────────────────────────────
  
  // net > 0 = capital migrating into L2 (risk-on liquidity)
  // net < 0 = capital returning to L1 (risk-off)
  
  const netUsd = metrics.netUsd ?? 0;
  const stableNet = metrics.stableNetUsd ?? 0;
  const whaleNet = metrics.whaleNetUsd ?? 0;
  
  let regime = 'NEUTRAL';
  
  if (hasUsd && eventCount >= 5) {
    // Strong directional moves
    if (netUsd > scaleUsd * 0.6) {
      regime = 'L2_RISK_ON';
    } else if (netUsd < -scaleUsd * 0.6) {
      regime = 'L1_FLIGHT';
    }
    
    // Stable-specific signals
    if (Math.abs(stableNet) > scaleUsd * 0.3 && Math.abs(whaleNet) < scaleUsd * 0.15) {
      regime = stableNet > 0 ? 'STABLE_DEPLOYMENT' : 'STABLE_WITHDRAWAL';
    }
    
    // Whale-specific signals
    if (Math.abs(whaleNet) > scaleUsd * 0.35) {
      regime = whaleNet > 0 ? 'WHALE_MIGRATION' : 'WHALE_EXIT';
      flags.push('BRIDGE_WHALE_SIGNAL');
    }
  }
  
  // ─────────────────────────────────────────────────────────────
  // DRIVERS
  // ─────────────────────────────────────────────────────────────
  
  if (metrics.netUsd !== null) {
    if (metrics.netUsd > 0) {
      drivers.push(`Strong L1→L2 migration (net +$${formatUsd(metrics.netUsd)})`);
    } else if (metrics.netUsd < 0) {
      drivers.push(`Capital returning to L1 (net -$${formatUsd(Math.abs(metrics.netUsd))})`);
    } else {
      drivers.push('Bridge flow balanced');
    }
  } else {
    drivers.push(`USD not available; direction from counts (net=${metrics.netCount})`);
  }
  
  // Stable driver
  if (metrics.stableNetUsd !== null && Math.abs(metrics.stableNetUsd) > scaleUsd * 0.15) {
    if (metrics.stableNetUsd > 0) {
      drivers.push(`Stable deployment to L2 (+$${formatUsd(metrics.stableNetUsd)})`);
    } else {
      drivers.push(`Stable withdrawal from L2 (-$${formatUsd(Math.abs(metrics.stableNetUsd))})`);
    }
    flags.push('BRIDGE_STABLE_SIGNAL');
  }
  
  // Whale driver
  if (metrics.whaleNetUsd !== null && Math.abs(metrics.whaleNetUsd) > scaleUsd * 0.25) {
    if (metrics.whaleNetUsd > 0) {
      drivers.push(`Whale migration detected (+$${formatUsd(metrics.whaleNetUsd)})`);
    } else {
      drivers.push(`Whale exit detected (-$${formatUsd(Math.abs(metrics.whaleNetUsd))})`);
    }
  }
  
  // Per-bridge breakdown driver
  const bridgeNames = Object.keys(input.byBridge);
  if (bridgeNames.length > 0) {
    const dominant = bridgeNames.reduce((a, b) => 
      Math.abs(input.byBridge[a]?.netUsd ?? 0) > Math.abs(input.byBridge[b]?.netUsd ?? 0) ? a : b
    );
    const dominantNet = input.byBridge[dominant]?.netUsd;
    if (dominantNet !== null && Math.abs(dominantNet) > scaleUsd * 0.2) {
      drivers.push(`${dominant} bridge most active`);
    }
  }
  
  return {
    score: {
      value: clamp(scoreValue, 0, 100),
      regime,
      confidence: Math.round(confidence * 100) / 100,
    },
    drivers: drivers.slice(0, 6),
    flags: Array.from(new Set(flags)).slice(0, 12),
  };
}

console.log('[OnChain V2] Bridge Score Engine loaded');
