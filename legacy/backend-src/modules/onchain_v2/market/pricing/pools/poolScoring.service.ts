/**
 * OnChain V2 — Pool Scoring Service
 * ===================================
 * 
 * STEP 2: Pool Scoring & Auto-Activation
 * 
 * Scores DEX pools based on:
 * - Liquidity (USD)
 * - Volume (24h)
 * - Activity (trades)
 * - Freshness (last swap)
 * - Fee tier preference
 * - TWAP deviation penalty
 */

import { DexPoolModel } from '../../../ingestion/dex/models';
import { SCORING } from './poolScoring.constants';
import { ONCHAIN_FLAGS } from '../../../core/featureFlags';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type PoolStatus = 'CANDIDATE' | 'ACTIVE' | 'DEGRADED' | 'DISABLED';

export interface ScoreBreakdown {
  liquidity: number;
  volume: number;
  activity: number;
  freshness: number;
  feeTier: number;
  deviation: number;
  reliability: number;  // STEP 4.1: TVL data reliability
  deviationBps: number;
}

export interface PoolScoreResult {
  poolId: string;
  score: number;
  confidence: number;
  status: PoolStatus;
  statusReason: string;
  breakdown: ScoreBreakdown;
  reasons: string[];  // PHASE 2.4: All reasons why pool is not ACTIVE
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

const clamp = (x: number, a: number, b: number) => Math.max(a, Math.min(b, x));

/**
 * Logarithmic scoring: 0..1 with soft cap at pivot
 */
function scoreLog(value: number, pivot: number): number {
  if (!value || value <= 0) return 0;
  const v = Math.log10(1 + value);
  const p = Math.log10(1 + pivot);
  return clamp(v / (2 * p), 0, 1);
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class PoolScoringService {
  
  /**
   * Score all pools for a chain and update status
   */
  async scorePoolsForChain(args: { 
    chainId: number; 
    limit?: number;
  }): Promise<{ ok: boolean; chainId: number; updated: number; summary: Record<PoolStatus, number> }> {
    const { chainId, limit = 5000 } = args;
    const now = Date.now();
    
    const pools = await DexPoolModel.find({ chainId }).limit(limit).lean();
    
    if (!pools.length) {
      return { ok: true, chainId, updated: 0, summary: { CANDIDATE: 0, ACTIVE: 0, DEGRADED: 0, DISABLED: 0 } };
    }
    
    const updates: any[] = [];
    const summary: Record<PoolStatus, number> = { CANDIDATE: 0, ACTIVE: 0, DEGRADED: 0, DISABLED: 0 };
    
    for (const p of pools) {
      const result = this.scorePool(p, now);
      summary[result.status]++;
      
      updates.push({
        updateOne: {
          filter: { _id: p._id },
          update: {
            $set: {
              score: result.score,
              confidence: result.confidence,
              status: result.status,
              statusReason: result.statusReason,
              scoreBreakdown: result.breakdown,
              updatedAt: now,
            },
          },
        },
      });
    }
    
    if (updates.length) {
      await DexPoolModel.bulkWrite(updates, { ordered: false });
    }
    
    return { ok: true, chainId, updated: updates.length, summary };
  }
  
  /**
   * Score a single pool
   * STEP 4.1: Enhanced with TVL reliability and hard thresholds
   */
  scorePool(pool: any, now: number = Date.now()): PoolScoreResult {
    const poolId = String(pool._id || pool.address);
    
    // Check freshness (last swap within 24h)
    const isFresh = pool.lastSwapAt && (now - pool.lastSwapAt) < 24 * 60 * 60 * 1000;
    
    // Check TVL freshness (updated within 1h)
    const hasFreshTvl = pool.tvlUpdatedAt && (now - pool.tvlUpdatedAt) < 60 * 60 * 1000;
    
    // Liquidity score (0..1) pivot 500K
    const liquidity = scoreLog(pool.liquidityUsd ?? 0, SCORING.LIQUIDITY_PIVOT_USD);
    
    // Volume score (0..1) pivot 50K
    const volume = scoreLog(pool.volume24hUsd ?? 0, SCORING.VOLUME_PIVOT_USD);
    
    // Activity score (0..1) pivot 200 trades
    const activity = scoreLog(pool.trades24h ?? 0, SCORING.TRADES_PIVOT);
    
    // Freshness score (0..1)
    const freshness = isFresh ? 1 : hasFreshTvl ? 0.5 : 0;
    
    // Fee tier preference
    const isStable = pool.isStablePair ?? false;
    const fee = pool.fee ?? 3000;
    const feeTier = isStable
      ? (fee <= 500 ? 1 : fee <= 3000 ? 0.6 : 0.3)
      : (fee === 3000 ? 1 : fee === 500 ? 0.7 : 0.5);
    
    // Deviation penalty (TWAP vs reference price)
    const deviationBps = pool.twapDeviationBps ?? 0;
    const deviation = clamp(1 - deviationBps / 200, 0, 1); // 200 bps -> 0
    
    // STEP 4.1: TVL data reliability
    const reliability = clamp(pool.tvlReliability ?? 0, 0, 1);
    
    // Weighted score
    const w = SCORING.WEIGHTS;
    const score01 = 
      w.liquidity * liquidity +
      w.volume * volume +
      w.activity * activity +
      w.freshness * freshness +
      w.feeTier * feeTier +
      w.deviation * deviation +
      w.reliability * reliability;
    
    const score = Math.round(100 * clamp(score01, 0, 1));
    
    // Confidence (independent of weights)
    const confidence = clamp(
      0.25 * liquidity + 0.25 * volume + 0.25 * activity + 0.25 * reliability,
      0, 1
    );
    
    // Status auto-activation
    // STEP 4.1: Added hard TVL/volume thresholds for ACTIVE status
    let status: PoolStatus;
    let statusReason: string;
    
    const liquidityUsd = pool.liquidityUsd ?? 0;
    const volumeUsd = pool.volume24hUsd ?? 0;
    
    const meetsScoreReqs = score >= SCORING.ACTIVE_SCORE_MIN && 
                           confidence >= SCORING.ACTIVE_CONFIDENCE_MIN && 
                           deviationBps <= SCORING.ACTIVE_DEV_MAX_BPS;
    
    const meetsTvlReqs = liquidityUsd >= SCORING.ACTIVE_LIQUIDITY_MIN_USD &&
                         volumeUsd >= SCORING.ACTIVE_VOLUME_MIN_USD;
    
    if (meetsScoreReqs && meetsTvlReqs) {
      // Phase 5.3: Auto-activation guard
      if (ONCHAIN_FLAGS.POOL_AUTO_ACTIVATION) {
        status = 'ACTIVE';
        statusReason = 'AUTO_ACTIVE';
      } else {
        status = 'DEGRADED';
        statusReason = 'AUTO_ACTIVATION_DISABLED';
      }
    } else if (meetsScoreReqs && !meetsTvlReqs) {
      status = 'DEGRADED';
      statusReason = liquidityUsd < SCORING.ACTIVE_LIQUIDITY_MIN_USD 
        ? 'LOW_TVL' 
        : 'LOW_VOLUME';
    } else if (
      score >= SCORING.DEGRADED_SCORE_MIN && 
      confidence >= SCORING.DEGRADED_CONFIDENCE_MIN
    ) {
      status = 'DEGRADED';
      statusReason = 'LOW_QUALITY';
    } else {
      status = 'DISABLED';
      statusReason = 'NO_LIQUIDITY_OR_STALE';
    }
    
    // PHASE 2.4: Build reasons array (why not ACTIVE)
    const reasons: string[] = [];
    if (score < SCORING.ACTIVE_SCORE_MIN) reasons.push(`score ${score} < ${SCORING.ACTIVE_SCORE_MIN}`);
    if (confidence < SCORING.ACTIVE_CONFIDENCE_MIN) reasons.push(`confidence ${confidence.toFixed(2)} < ${SCORING.ACTIVE_CONFIDENCE_MIN}`);
    if (deviationBps > SCORING.ACTIVE_DEV_MAX_BPS) reasons.push(`deviation ${deviationBps}bps > ${SCORING.ACTIVE_DEV_MAX_BPS}bps`);
    if (liquidityUsd < SCORING.ACTIVE_LIQUIDITY_MIN_USD) reasons.push(`tvl $${(liquidityUsd/1e6).toFixed(2)}M < $${SCORING.ACTIVE_LIQUIDITY_MIN_USD/1e6}M`);
    if (volumeUsd < SCORING.ACTIVE_VOLUME_MIN_USD) reasons.push(`volume $${(volumeUsd/1e3).toFixed(0)}K < $${SCORING.ACTIVE_VOLUME_MIN_USD/1e3}K`);
    if (!isFresh) reasons.push('no recent swap (>24h)');
    if (!hasFreshTvl) reasons.push('tvl data stale (>1h)');

    return {
      poolId,
      score,
      confidence,
      status,
      statusReason,
      reasons,
      breakdown: {
        liquidity,
        volume,
        activity,
        freshness,
        feeTier,
        deviation,
        reliability,
        deviationBps,
      },
    };
  }
  
  /**
   * Get scoring stats for a chain
   */
  async getStats(chainId: number): Promise<{
    total: number;
    byStatus: Record<PoolStatus, number>;
    avgScore: number;
    avgConfidence: number;
  }> {
    const stats = await DexPoolModel.aggregate([
      { $match: { chainId } },
      {
        $group: {
          _id: '$status',
          count: { $sum: 1 },
          avgScore: { $avg: '$score' },
          avgConfidence: { $avg: '$confidence' },
        },
      },
    ]);
    
    const byStatus: Record<PoolStatus, number> = { CANDIDATE: 0, ACTIVE: 0, DEGRADED: 0, DISABLED: 0 };
    let total = 0;
    let totalScore = 0;
    let totalConf = 0;
    
    for (const s of stats) {
      const status = (s._id || 'CANDIDATE') as PoolStatus;
      byStatus[status] = s.count;
      total += s.count;
      totalScore += (s.avgScore || 0) * s.count;
      totalConf += (s.avgConfidence || 0) * s.count;
    }
    
    return {
      total,
      byStatus,
      avgScore: total > 0 ? Math.round(totalScore / total) : 0,
      avgConfidence: total > 0 ? +(totalConf / total).toFixed(3) : 0,
    };
  }
}

export const poolScoringService = new PoolScoringService();

console.log('[OnChain V2] Pool Scoring Service loaded');
