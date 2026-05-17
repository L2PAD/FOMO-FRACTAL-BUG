/**
 * OnChain V2 — Normalizer Service
 * =================================
 * 
 * BLOCK 6: Converts raw module outputs to unified NormalizedSignal format.
 * Each module has its own scaling and interpretation.
 */

import { NormalizedSignal, NormalizeOptions, DEFAULT_SCALES } from './normalizer.types.js';
import { tanhNorm, toScore, toDirection, toStrength, clamp01 } from './normalizer.math.js';

export class NormalizerService {
  
  /**
   * Normalize Market liquidity score
   * Input: 0-100 score where 50 is neutral
   */
  normalizeMarket(
    marketScore: number,
    confidence: number,
    drivers: string[] = [],
    flags: string[] = [],
    raw?: any,
    opt?: NormalizeOptions
  ): NormalizedSignal {
    const delta = (marketScore ?? 50) - 50;
    const scale = opt?.scale ?? DEFAULT_SCALES.market.scale;
    const norm = tanhNorm(delta, scale);
    
    return {
      key: 'market',
      score: toScore(norm),
      direction: toDirection(norm, opt?.deadzone ?? 0.05),
      strength: toStrength(norm),
      confidence: clamp01(confidence ?? 0),
      drivers,
      flags,
      raw,
    };
  }

  /**
   * Normalize Flow imbalance
   * Input: percent imbalance (-100 to +100)
   * Positive = buying pressure, Negative = selling pressure
   */
  normalizeFlow(
    flowImbalancePct: number,
    confidence: number,
    drivers: string[] = [],
    flags: string[] = [],
    raw?: any,
    opt?: NormalizeOptions
  ): NormalizedSignal {
    const scale = opt?.scale ?? DEFAULT_SCALES.flow.scale;
    const norm = tanhNorm(flowImbalancePct ?? 0, scale);
    
    return {
      key: 'flow',
      score: toScore(norm),
      direction: toDirection(norm, opt?.deadzone ?? 0.05),
      strength: toStrength(norm),
      confidence: clamp01(confidence ?? 0),
      drivers,
      flags,
      raw,
    };
  }

  /**
   * Normalize Bridge net migration
   * Input: USD net (L1→L2 minus L2→L1)
   * Positive = capital moving to L2 (risk-on), Negative = capital fleeing to L1
   */
  normalizeBridge(
    netUsd: number,
    confidence: number,
    drivers: string[] = [],
    flags: string[] = [],
    raw?: any,
    opt?: NormalizeOptions
  ): NormalizedSignal {
    const scale = opt?.scale ?? DEFAULT_SCALES.bridge.scale;
    const norm = tanhNorm(netUsd ?? 0, scale);
    
    return {
      key: 'bridge',
      score: toScore(norm),
      direction: toDirection(norm, opt?.deadzone ?? 0.05),
      strength: toStrength(norm),
      confidence: clamp01(confidence ?? 0),
      drivers,
      flags,
      raw,
    };
  }

  /**
   * Normalize Stablecoins supply change
   * Input: USD net (mint minus burn)
   * Positive = supply expanding (liquidity injection), Negative = contracting
   */
  normalizeStables(
    netUsd: number,
    confidence: number,
    drivers: string[] = [],
    flags: string[] = [],
    raw?: any,
    opt?: NormalizeOptions
  ): NormalizedSignal {
    const scale = opt?.scale ?? DEFAULT_SCALES.stables.scale;
    const norm = tanhNorm(netUsd ?? 0, scale);
    
    return {
      key: 'stables',
      score: toScore(norm),
      direction: toDirection(norm, opt?.deadzone ?? 0.05),
      strength: toStrength(norm),
      confidence: clamp01(confidence ?? 0),
      drivers,
      flags,
      raw,
    };
  }

  /**
   * Normalize any custom signal
   */
  normalizeCustom(
    key: string,
    value: number,
    scale: number,
    confidence: number,
    drivers: string[] = [],
    flags: string[] = [],
    raw?: any,
    opt?: NormalizeOptions
  ): NormalizedSignal {
    const norm = tanhNorm(value, scale);
    
    return {
      key,
      score: toScore(norm),
      direction: toDirection(norm, opt?.deadzone ?? 0.05),
      strength: toStrength(norm),
      confidence: clamp01(confidence ?? 0),
      drivers,
      flags,
      raw,
    };
  }
}

// Singleton
export const normalizerService = new NormalizerService();

console.log('[OnChain V2] Normalizer service loaded');
