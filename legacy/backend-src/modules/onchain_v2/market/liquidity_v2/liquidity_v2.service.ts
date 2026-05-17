/**
 * OnChain V2 — LiquidityScore v2 Service
 * ========================================
 * 
 * BLOCK 7: Orchestrates data collection, normalization, and storage.
 */

import { normalizerService } from '../../normalization/normalizer.service.js';
import { buildLareV2, type LareV2Output } from './liquidity_v2.engine.js';
import { LARE_V2_VERSION, type LareV2Window } from './liquidity_v2.contracts.js';
import { LareV2Model } from './liquidity_v2.model.js';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function align10m(ts: number): number {
  const m = 10 * 60 * 1000;
  return Math.floor(ts / m) * m;
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export interface LiquidityV2Deps {
  marketLiquidity: {
    getLatest: (window: string) => Promise<any>;
  };
  bridgeAgg: {
    getLatest: (window: string) => Promise<any>;
  };
  stablesAgg: {
    getLatest: (window: string) => Promise<any>;
  };
}

export class LiquidityV2Service {
  constructor(private deps: LiquidityV2Deps) {}

  /**
   * Compute and store LARE v2 for given window
   */
  async computeAndStore(window: LareV2Window, chainId: number = 1): Promise<LareV2Output> {
    const now = Date.now();
    const bucketTs = align10m(now);

    // Fetch latest from each module
    const [marketLatest, bridgeLatest, stablesLatest] = await Promise.all([
      this.deps.marketLiquidity.getLatest(window).catch(() => null),
      this.deps.bridgeAgg.getLatest(window).catch(() => null),
      this.deps.stablesAgg.getLatest(window).catch(() => null),
    ]);

    // Normalize Market
    const marketSig = normalizerService.normalizeMarket(
      marketLatest?.score?.value ?? marketLatest?.score ?? 50,
      marketLatest?.score?.confidence ?? marketLatest?.confidence ?? 0.2,
      marketLatest?.drivers ?? [],
      marketLatest?.flags ?? [],
      { bucketTs: marketLatest?.bucketTs }
    );

    // Flow: extracted from market liquidity or DEX data
    // For now, derive from market imbalance if available
    const flowImbalance = marketLatest?.dexImbalancePct ?? 0;
    const flowConfidence = flowImbalance !== 0 ? 0.4 : 0.1;
    const flowSig = normalizerService.normalizeFlow(
      flowImbalance,
      flowConfidence,
      flowImbalance > 10 ? ['Net DEX buying pressure'] : 
      flowImbalance < -10 ? ['Net DEX selling pressure'] : ['Flow balanced'],
      flowImbalance === 0 ? ['FLOW_LIMITED_DATA'] : [],
      { source: 'market_derived' }
    );

    // Normalize Bridge
    const bridgeSig = normalizerService.normalizeBridge(
      bridgeLatest?.metrics?.netUsd ?? 0,
      bridgeLatest?.score?.confidence ?? 0,
      bridgeLatest?.drivers ?? [],
      bridgeLatest?.flags ?? [],
      { bucketTs: bridgeLatest?.bucketTs }
    );

    // Normalize Stables
    const stablesSig = normalizerService.normalizeStables(
      stablesLatest?.metrics?.netUsd ?? 0,
      stablesLatest?.score?.confidence ?? 0,
      stablesLatest?.drivers ?? [],
      stablesLatest?.flags ?? [],
      { bucketTs: stablesLatest?.bucketTs }
    );

    // Build composite
    const output = buildLareV2(window, bucketTs, [marketSig, flowSig, bridgeSig, stablesSig]);

    // Persist
    await LareV2Model.updateOne(
      { chainId, window, bucketTs },
      { $set: { ...output, chainId } },
      { upsert: true }
    );

    return output;
  }

  /**
   * Get latest LARE v2 for window
   */
  async getLatest(window: LareV2Window, chainId: number = 1): Promise<LareV2Output | null> {
    const doc = await LareV2Model
      .findOne({ chainId, window })
      .sort({ bucketTs: -1 })
      .lean();
    
    if (!doc) return null;
    
    return {
      version: doc.version,
      window: doc.window as LareV2Window,
      bucketTs: doc.bucketTs,
      computedAt: doc.updatedAt?.getTime() ?? Date.now(),
      score: doc.score,
      confidence: doc.confidence,
      regime: doc.regime as any,
      gate: doc.gate,
      components: doc.components,
      drivers: doc.drivers,
      flags: doc.flags,
    };
  }

  /**
   * Get series for charting
   */
  async getSeries(window: LareV2Window, range: '24h' | '7d' | '30d' = '30d', chainId: number = 1) {
    const ms = 
      range === '24h' ? 24 * 60 * 60 * 1000 :
      range === '7d' ? 7 * 24 * 60 * 60 * 1000 :
      30 * 24 * 60 * 60 * 1000;
    
    const from = Date.now() - ms;

    const docs = await LareV2Model
      .find({
        chainId,
        window,
        bucketTs: { $gte: from },
      })
      .sort({ bucketTs: 1 })
      .select('bucketTs score confidence regime gate.riskCap -_id')
      .lean();

    return docs.map(d => ({
      t: d.bucketTs,
      score: d.score,
      confidence: d.confidence,
      regime: d.regime,
      riskCap: d.gate?.riskCap ?? 0.14,
    }));
  }

  /**
   * Get health status
   */
  async getHealth() {
    const [latest24, latest7] = await Promise.all([
      this.getLatest('24h'),
      this.getLatest('7d'),
    ]);

    const now = Date.now();
    const stale24 = latest24 ? (now - latest24.bucketTs > 30 * 60 * 1000) : true;
    const stale7 = latest7 ? (now - latest7.bucketTs > 30 * 60 * 1000) : true;

    return {
      ok: !stale24 || !stale7,
      version: LARE_V2_VERSION,
      windows: {
        '24h': latest24 ? {
          bucketTs: latest24.bucketTs,
          score: latest24.score,
          confidence: latest24.confidence,
          regime: latest24.regime,
          stale: stale24,
        } : null,
        '7d': latest7 ? {
          bucketTs: latest7.bucketTs,
          score: latest7.score,
          confidence: latest7.confidence,
          regime: latest7.regime,
          stale: stale7,
        } : null,
      },
      ts: now,
    };
  }
}

console.log('[OnChain V2] LiquidityScore v2 service loaded');
