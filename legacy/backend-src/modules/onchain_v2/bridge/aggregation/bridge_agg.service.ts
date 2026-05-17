/**
 * OnChain V2 — Bridge Aggregation Service
 * =========================================
 * 
 * Computes and stores bridge migration aggregates.
 * Queries events, aggregates metrics, computes score.
 */

import { BridgeAggregateModel, BridgeAggWindow, BridgeMetrics, BridgeByBridge } from './bridge_agg.model.js';
import { computeBridgeScore, BridgeScoreInput } from './bridge_agg.engine.js';
import { BridgeEventModel } from '../bridge.model.js';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function alignTo10Min(ts: number): number {
  const step = 10 * 60 * 1000;
  return Math.floor(ts / step) * step;
}

function windowMs(window: BridgeAggWindow): number {
  return window === '24h' 
    ? 24 * 60 * 60 * 1000 
    : 7 * 24 * 60 * 60 * 1000;
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class BridgeAggregationService {
  
  /**
   * Compute aggregates for a time window and upsert to DB
   */
  async computeAndUpsert(window: BridgeAggWindow, nowTs = Date.now(), chainId: number = 1): Promise<any> {
    const bucketTs = alignTo10Min(nowTs);
    const since = nowTs - windowMs(window);
    
    // Pull events from window
    const events = await BridgeEventModel.find({
      timestamp: { $gte: since, $lte: nowTs },
    })
      .lean()
      .limit(200_000);
    
    // Initialize aggregation
    let inCount = 0, outCount = 0;
    let inUsd = 0, outUsd = 0;
    let stableInUsd = 0, stableOutUsd = 0;
    let whaleInUsd = 0, whaleOutUsd = 0;
    
    let hasUsd = true;
    let hasStable = true;
    let hasWhale = true;
    
    const byBridge: Record<string, BridgeByBridge> = {};
    
    // Process events
    for (const e of events) {
      const direction = e.direction as 'L1_TO_L2' | 'L2_TO_L1';
      const bridge = e.bridge || 'UNKNOWN';
      
      // Initialize bridge bucket
      if (!byBridge[bridge]) {
        byBridge[bridge] = {
          inCount: 0, outCount: 0, netCount: 0,
          inUsd: 0, outUsd: 0, netUsd: 0,
        };
      }
      
      // Get USD value (may be null)
      const usd: number | null = typeof e.usdValue === 'number' ? e.usdValue : null;
      if (usd === null) hasUsd = false;
      
      // Get flags
      const isStable = typeof e.isStable === 'boolean' ? e.isStable : false;
      const isWhale = typeof e.isWhale === 'boolean' ? e.isWhale : false;
      if (typeof e.isStable !== 'boolean') hasStable = false;
      if (typeof e.isWhale !== 'boolean') hasWhale = false;
      
      // Aggregate by direction
      if (direction === 'L1_TO_L2') {
        inCount++;
        byBridge[bridge].inCount++;
        
        if (usd !== null) {
          inUsd += usd;
          byBridge[bridge].inUsd = (byBridge[bridge].inUsd ?? 0) + usd;
          
          if (isStable) stableInUsd += usd;
          if (isWhale) whaleInUsd += usd;
        }
      } else if (direction === 'L2_TO_L1') {
        outCount++;
        byBridge[bridge].outCount++;
        
        if (usd !== null) {
          outUsd += usd;
          byBridge[bridge].outUsd = (byBridge[bridge].outUsd ?? 0) + usd;
          
          if (isStable) stableOutUsd += usd;
          if (isWhale) whaleOutUsd += usd;
        }
      }
    }
    
    // Compute net values
    const netCount = inCount - outCount;
    
    // Finalize metrics (null if USD missing)
    const metrics: BridgeMetrics = {
      inCount,
      outCount,
      netCount,
      
      inUsd: hasUsd ? inUsd : null,
      outUsd: hasUsd ? outUsd : null,
      netUsd: hasUsd ? (inUsd - outUsd) : null,
      
      stableInUsd: hasUsd ? stableInUsd : null,
      stableOutUsd: hasUsd ? stableOutUsd : null,
      stableNetUsd: hasUsd ? (stableInUsd - stableOutUsd) : null,
      
      whaleInUsd: hasUsd ? whaleInUsd : null,
      whaleOutUsd: hasUsd ? whaleOutUsd : null,
      whaleNetUsd: hasUsd ? (whaleInUsd - whaleOutUsd) : null,
    };
    
    // Finalize byBridge
    for (const bridge of Object.keys(byBridge)) {
      const b = byBridge[bridge];
      b.netCount = b.inCount - b.outCount;
      
      if (hasUsd) {
        b.netUsd = (b.inUsd ?? 0) - (b.outUsd ?? 0);
      } else {
        b.inUsd = null;
        b.outUsd = null;
        b.netUsd = null;
      }
    }
    
    // Compute score
    const scoreInput: BridgeScoreInput = {
      window,
      computedAt: nowTs,
      bucketTs,
      metrics,
      byBridge,
      hasUsd,
      hasStable,
      hasWhale,
      eventCount: events.length,
    };
    
    const { score, drivers, flags } = computeBridgeScore(scoreInput);
    
    // Build document
    const doc = {
      window,
      bucketTs,
      computedAt: nowTs,
      metrics,
      byBridge,
      score,
      drivers,
      flags,
    };
    
    // Upsert
    await BridgeAggregateModel.updateOne(
      { chainId, window, bucketTs },
      { $set: { ...doc, chainId } },
      { upsert: true }
    );
    
    return doc;
  }
  
  /**
   * Get latest aggregate for window
   */
  async getLatest(window: BridgeAggWindow, chainId: number = 1): Promise<any | null> {
    return BridgeAggregateModel
      .findOne({ chainId, window })
      .sort({ bucketTs: -1 })
      .lean();
  }
  
  /**
   * Get series for charting
   */
  async getSeries(
    window: BridgeAggWindow,
    range: '24h' | '7d' | '30d' = '30d',
    chainId: number = 1
  ): Promise<any[]> {
    const now = Date.now();
    const rangeMs = 
      range === '24h' ? 24 * 60 * 60 * 1000 :
      range === '7d' ? 7 * 24 * 60 * 60 * 1000 :
      30 * 24 * 60 * 60 * 1000;
    
    return BridgeAggregateModel
      .find({
        chainId,
        window,
        bucketTs: { $gte: now - rangeMs },
      })
      .sort({ bucketTs: 1 })
      .select('bucketTs score.value score.regime metrics.netUsd metrics.netCount -_id')
      .lean();
  }
  
  /**
   * Get health status
   */
  async getHealth(): Promise<{
    ok: boolean;
    latest: {
      '24h': { bucketTs: number; score: any } | null;
      '7d': { bucketTs: number; score: any } | null;
    };
  }> {
    const latest24h = await this.getLatest('24h');
    const latest7d = await this.getLatest('7d');
    
    return {
      ok: true,
      latest: {
        '24h': latest24h ? { bucketTs: latest24h.bucketTs, score: latest24h.score } : null,
        '7d': latest7d ? { bucketTs: latest7d.bucketTs, score: latest7d.score } : null,
      },
    };
  }
}

// Singleton
export const bridgeAggregationService = new BridgeAggregationService();

console.log('[OnChain V2] Bridge Aggregation Service loaded');
