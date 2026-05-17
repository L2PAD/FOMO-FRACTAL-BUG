/**
 * OnChain V2 — Stablecoin Aggregation Service
 * =============================================
 * 
 * Computes mint/burn aggregates and score.
 */

import { StableAggregateModel, StableAggWindow, StableMetrics, StableScore } from './stable_aggregate.model.js';
import { StableMintBurnModel } from './stable_mintburn.model.js';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function alignTo10Min(ts: number): number {
  const step = 10 * 60 * 1000;
  return Math.floor(ts / step) * step;
}

function windowMs(window: StableAggWindow): number {
  switch (window) {
    case '24h': return 24 * 60 * 60 * 1000;
    case '7d': return 7 * 24 * 60 * 60 * 1000;
    case '30d': return 30 * 24 * 60 * 60 * 1000;
  }
}

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
// SCALE CONSTANTS
// ═══════════════════════════════════════════════════════════════

const SCALE_USD = {
  '24h': 100_000_000,   // $100M
  '7d': 500_000_000,    // $500M
  '30d': 2_000_000_000, // $2B
};

// ═══════════════════════════════════════════════════════════════
// SCORE ENGINE
// ═══════════════════════════════════════════════════════════════

function computeStableScore(
  window: StableAggWindow,
  metrics: StableMetrics,
  eventCount: number,
  chainsCovered: number
): { score: StableScore; drivers: string[]; flags: string[] } {
  const flags: string[] = [];
  const drivers: string[] = [];

  // Confidence
  let confidence = 0.2;
  
  if (eventCount >= 10) confidence += 0.15;
  if (eventCount >= 50) confidence += 0.15;
  if (eventCount >= 200) confidence += 0.10;
  
  if (chainsCovered >= 2) confidence += 0.10;
  if (chainsCovered >= 4) confidence += 0.10;
  
  if (eventCount < 5) {
    flags.push('STABLE_LOW_DATA');
    confidence *= 0.5;
  }
  
  if (chainsCovered === 1) {
    flags.push('STABLE_SINGLE_CHAIN_ONLY');
  }
  
  confidence = clamp(confidence, 0, 1);

  // Direction score
  const scale = SCALE_USD[window];
  const netUsd = metrics.netUsd ?? metrics.netAmount; // Fallback to token units
  
  const x = clamp(netUsd / scale, -3, 3);
  const direction01 = (tanh(x) + 1) / 2;
  const dampedDirection = 0.5 + (direction01 - 0.5) * clamp(confidence + 0.2, 0.2, 1);
  const scoreValue = Math.round(100 * dampedDirection);

  // Regime
  let regime = 'NEUTRAL';
  if (netUsd > scale * 0.3) regime = 'SUPPLY_EXPANDING';
  if (netUsd < -scale * 0.3) regime = 'SUPPLY_CONTRACTING';

  // Drivers
  if (metrics.netUsd !== null) {
    if (metrics.netUsd > 0) {
      drivers.push(`Stable supply expanding (+$${formatUsd(metrics.netUsd)} net mint)`);
    } else if (metrics.netUsd < 0) {
      drivers.push(`Stable supply contracting (-$${formatUsd(Math.abs(metrics.netUsd))} net burn)`);
    } else {
      drivers.push('Stable supply balanced');
    }
  } else {
    drivers.push(`Stable supply: net ${formatUsd(metrics.netAmount)} tokens`);
  }

  if (metrics.mintCount > 0) {
    drivers.push(`${metrics.mintCount} mint events`);
  }
  if (metrics.burnCount > 0) {
    drivers.push(`${metrics.burnCount} burn events`);
  }

  return {
    score: {
      value: clamp(scoreValue, 0, 100),
      regime,
      confidence: Math.round(confidence * 100) / 100,
    },
    drivers: drivers.slice(0, 4),
    flags: Array.from(new Set(flags)),
  };
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class StableAggregationService {
  
  /**
   * Compute and upsert aggregate for window
   */
  async computeAndUpsert(window: StableAggWindow, nowTs = Date.now(), chainId: number = 1): Promise<any> {
    const bucketTs = alignTo10Min(nowTs);
    const since = nowTs - windowMs(window);

    // Pull events
    const events = await StableMintBurnModel.find({
      timestamp: { $gte: since, $lte: nowTs },
    })
      .lean()
      .limit(500_000);

    // Aggregate
    let mintCount = 0, burnCount = 0;
    let mintAmount = 0, burnAmount = 0;
    let mintUsd = 0, burnUsd = 0;
    
    const chains = new Set<number>();
    const byToken: Record<string, any> = {};

    for (const e of events) {
      chains.add(e.chainId);
      
      const token = e.token || 'UNKNOWN';
      if (!byToken[token]) {
        byToken[token] = { mintCount: 0, burnCount: 0, mintAmount: 0, burnAmount: 0, netAmount: 0 };
      }

      if (e.direction === 'MINT') {
        mintCount++;
        mintAmount += e.amount || 0;
        mintUsd += e.usdAmount || 0;
        byToken[token].mintCount++;
        byToken[token].mintAmount += e.amount || 0;
      } else if (e.direction === 'BURN') {
        burnCount++;
        burnAmount += e.amount || 0;
        burnUsd += e.usdAmount || 0;
        byToken[token].burnCount++;
        byToken[token].burnAmount += e.amount || 0;
      }
    }

    // Finalize by token
    for (const token of Object.keys(byToken)) {
      byToken[token].netAmount = byToken[token].mintAmount - byToken[token].burnAmount;
    }

    const chainsCovered = chains.size;
    const netAmount = mintAmount - burnAmount;
    const netUsd = mintUsd - burnUsd;

    const metrics: StableMetrics = {
      mintCount,
      burnCount,
      mintAmount,
      burnAmount,
      netAmount,
      mintUsd: events.length > 0 ? mintUsd : null,
      burnUsd: events.length > 0 ? burnUsd : null,
      netUsd: events.length > 0 ? netUsd : null,
    };

    const { score, drivers, flags } = computeStableScore(
      window,
      metrics,
      events.length,
      chainsCovered
    );

    const doc = {
      window,
      bucketTs,
      computedAt: nowTs,
      chainsCovered,
      metrics,
      byToken,
      score,
      drivers,
      flags,
    };

    await StableAggregateModel.updateOne(
      { chainId, window, bucketTs },
      { $set: { ...doc, chainId } },
      { upsert: true }
    );

    return doc;
  }

  /**
   * Get latest aggregate
   */
  async getLatest(window: StableAggWindow, chainId: number = 1): Promise<any | null> {
    return StableAggregateModel
      .findOne({ chainId, window })
      .sort({ bucketTs: -1 })
      .lean();
  }

  /**
   * Get series for charting
   */
  async getSeries(window: StableAggWindow, range: '24h' | '7d' | '30d' = '30d', chainId: number = 1): Promise<any[]> {
    const now = Date.now();
    const rangeMs = 
      range === '24h' ? 24 * 60 * 60 * 1000 :
      range === '7d' ? 7 * 24 * 60 * 60 * 1000 :
      30 * 24 * 60 * 60 * 1000;

    return StableAggregateModel
      .find({
        chainId,
        window,
        bucketTs: { $gte: now - rangeMs },
      })
      .sort({ bucketTs: 1 })
      .select('bucketTs score.value score.regime metrics.netUsd metrics.netAmount -_id')
      .lean();
  }

  /**
   * Get health
   */
  async getHealth(): Promise<{
    ok: boolean;
    latest: {
      '24h': { bucketTs: number; score: any } | null;
      '7d': { bucketTs: number; score: any } | null;
      '30d': { bucketTs: number; score: any } | null;
    };
  }> {
    const [l24, l7, l30] = await Promise.all([
      this.getLatest('24h'),
      this.getLatest('7d'),
      this.getLatest('30d'),
    ]);

    return {
      ok: true,
      latest: {
        '24h': l24 ? { bucketTs: l24.bucketTs, score: l24.score } : null,
        '7d': l7 ? { bucketTs: l7.bucketTs, score: l7.score } : null,
        '30d': l30 ? { bucketTs: l30.bucketTs, score: l30.score } : null,
      },
    };
  }
}

// Singleton
export const stableAggregationService = new StableAggregationService();

console.log('[OnChain V2] Stable Aggregation Service loaded');
