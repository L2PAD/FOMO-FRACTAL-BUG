/**
 * OnChain V2 — AltFlow Aggregator Service v2
 * ===========================================
 * 
 * PHASE 3.5.3: Real token aggregation from normalized flows
 * STEP 3: Confidence hardening with quality/evidence/flags
 */

import { TokenFlowModel } from '../flow/flow.model';
import { tokenMetaService } from '../flow/tokenMeta.service';
import { AltFlowPointModel } from './altflow.model';
import { 
  computeAltflowConfidence, 
  type PriceSource, 
  type PoolStatus,
  type AltflowFlag,
} from './altflow.confidence';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type AltflowWindow = '24h' | '7d';

export interface AltflowQuality {
  priceSource: PriceSource;
  priceConfidence: number | null;
  poolStatus: PoolStatus;
  poolScore: number;
}

export interface AltflowEvidence {
  trades: number;
  uniquePools: number;
  spanHours: number;
  pricedShare: number;
}

export interface AltflowRankingRow {
  chainId: number;
  tokenAddress: string;
  tokenSymbol: string;
  
  buyUsd: number;
  sellUsd: number;
  netUsd: number;
  totalUsd: number;
  buySellRatio: number;
  
  score: number;       // 0..100
  confidence: number;  // 0..1
  side: 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL';
  passesStrongOnly?: boolean; // PHASE 2.5: strong-only gate result
  
  // STEP 3: Enhanced fields
  quality: AltflowQuality;
  evidence: AltflowEvidence;
  components: {
    dexNetUsd: number;
    cexNetUsd: number;
    whaleNetUsd: number;
  };
  
  drivers: string[];
  flags: AltflowFlag[];
  
  lastTs: number;
  totalCount: number;
}

export interface AltflowResult {
  ok: boolean;
  window: AltflowWindow;
  chainId: number;
  updatedAt: number;
  rows: AltflowRankingRow[];
  meta: {
    tokenCount: number;
    labelsCoverage: number;
    avgConfidence: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const WINDOW_MS: Record<AltflowWindow, number> = {
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
};

const SCALE_USD: Record<AltflowWindow, number> = {
  '24h': 250_000,
  '7d': 2_000_000,
};

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function tanhNorm(x: number, scale: number): number {
  if (!Number.isFinite(x) || scale === 0) return 0;
  return Math.tanh(x / scale);
}

function computeScore(totalUsd: number, netUsd: number, scaleUsd: number): number {
  const volumeStrength = tanhNorm(totalUsd, scaleUsd);
  const netStrength = tanhNorm(netUsd, scaleUsd);
  const raw = (0.75 * netStrength) + (0.25 * volumeStrength * Math.sign(netStrength || 0));
  return clamp(Math.round((raw + 1) * 50), 0, 100);
}

function computeConfidence(totalUsd: number, totalCount: number, lastTs: number, now: number): number {
  const cVol = clamp(Math.log10(1 + totalUsd) / 6, 0, 1);
  const cCount = clamp(totalCount / 50, 0, 1);
  const ageH = (now - lastTs) / 3600000;
  const cFresh = ageH <= 2 ? 1 : ageH <= 12 ? 0.6 : 0.3;
  return clamp(0.55 * cVol + 0.30 * cCount + 0.15 * cFresh, 0, 1);
}

function computeDriversFlags(
  totalUsd: number, 
  netUsd: number, 
  totalCount: number, 
  lastTs: number, 
  now: number, 
  confidence: number,
  symbolSource: string
): { drivers: string[]; flags: AltflowFlag[] } {
  const drivers: string[] = [];
  const flags: AltflowFlag[] = [];
  const ageH = (now - lastTs) / 3600000;

  if (totalUsd >= 1_000_000) drivers.push('High volume (>$1M)');
  else if (totalUsd >= 500_000) drivers.push('Moderate volume');
  
  if (netUsd >= 500_000) drivers.push('Strong buy pressure');
  else if (netUsd >= 100_000) drivers.push('Net buying');
  else if (netUsd <= -500_000) drivers.push('Strong sell pressure');
  else if (netUsd <= -100_000) drivers.push('Net selling');

  if (totalCount < 5) flags.push({ code: 'LOW_EVENTS', severity: 'WARN' });
  if (confidence < 0.25) flags.push({ code: 'LOW_CONFIDENCE', severity: 'WARN' });
  if (ageH > 24) flags.push({ code: 'STALE', severity: 'INFO' });
  if (symbolSource === 'unknown') flags.push({ code: 'SYMBOL_UNKNOWN', severity: 'INFO' });

  return { drivers, flags };
}

function determineSide(score: number): 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL' {
  if (score >= 60) return 'ACCUMULATION';
  if (score <= 40) return 'DISTRIBUTION';
  return 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class AltflowAggregateService {
  
  /**
   * Compute and return aggregated altflow data
   * P0.7: Added optional entityId filter for entity overlay
   */
  async compute(window: AltflowWindow, chainId: number, entityId?: string): Promise<AltflowResult> {
    const now = Date.now();
    const since = now - WINDOW_MS[window];
    const scaleUsd = SCALE_USD[window];
    
    // Build match stage with optional entity filter
    const matchStage: any = { chainId, blockTime: { $gte: since } };
    if (entityId) {
      matchStage.counterpartyEntityId = entityId;
    }
    
    // Aggregate flows by token with extended stats for STEP 3
    const agg = await TokenFlowModel.aggregate([
      { $match: matchStage },
      {
        $group: {
          _id: '$tokenAddress',
          buyUsd: { $sum: { $cond: [{ $eq: ['$side', 'BUY'] }, '$usdVolume', 0] } },
          sellUsd: { $sum: { $cond: [{ $eq: ['$side', 'SELL'] }, '$usdVolume', 0] } },
          totalCount: { $sum: 1 },
          pricedCount: { $sum: { $cond: [{ $gt: ['$usdVolume', 0] }, 1, 0] } },
          lastTs: { $max: '$blockTime' },
          firstTs: { $min: '$blockTime' },
          symbols: { $addToSet: '$tokenSymbol' },
          pools: { $addToSet: '$poolAddress' },
          priceSources: { $addToSet: '$usdSource' },
        },
      },
      { $addFields: { totalUsd: { $add: ['$buyUsd', '$sellUsd'] } } },
      { $match: { totalUsd: { $gte: 1000 } } }, // Min $1K volume
      { $sort: { totalUsd: -1 } },
      { $limit: 200 },
    ]);
    
    // Enrich with token metadata and compute scores
    const rows: AltflowRankingRow[] = [];
    let labeledCount = 0;
    let totalConfidence = 0;
    
    for (const r of agg) {
      const tokenAddress = String(r._id);
      const buyUsd = Number(r.buyUsd || 0);
      const sellUsd = Number(r.sellUsd || 0);
      const totalUsd = Number(r.totalUsd || (buyUsd + sellUsd));
      const netUsd = buyUsd - sellUsd;
      const buySellRatio = buyUsd / Math.max(sellUsd, 1);
      const totalCount = Number(r.totalCount || 0);
      const pricedCount = Number(r.pricedCount || 0);
      const lastTs = Number(r.lastTs || now);
      const firstTs = Number(r.firstTs || now);
      const uniquePools = (r.pools || []).filter((p: any) => p).length;
      
      // Calculate evidence
      const spanHours = Math.max(0, (lastTs - firstTs) / (1000 * 60 * 60));
      const pricedShare = totalCount > 0 ? pricedCount / totalCount : 0;
      
      // Determine price source (best available)
      const sources = (r.priceSources || []).filter((s: any) => s);
      let priceSource: PriceSource = 'NONE';
      if (sources.includes('CHAINLINK')) priceSource = 'CHAINLINK';
      else if (sources.includes('TWAP')) priceSource = 'TWAP';
      else if (sources.includes('DEX_VWAP')) priceSource = 'DEX_VWAP';
      
      // Get token symbol from metadata
      const meta = await tokenMetaService.get(chainId, tokenAddress);
      const tokenSymbol = meta.symbol;
      
      if (meta.source !== 'unknown') labeledCount++;
      
      const score = computeScore(totalUsd, netUsd, scaleUsd);
      const side = determineSide(score);
      
      // STEP 3: Enhanced confidence calculation
      const { confidence, flags: confFlags } = computeAltflowConfidence({
        priceSource,
        priceConfidence: null, // Could enhance with actual pricing service confidence
        poolStatus: 'UNKNOWN' as PoolStatus, // Could enhance with bestPoolResolver
        poolScore: 50, // Default mid score
        trades: totalCount,
        spanHours,
        pricedShare,
        dexNetUsd: netUsd,
        cexNetUsd: 0, // CEX not tracked separately yet
        whaleNetUsd: 0, // Whale not tracked separately yet
      });
      
      // Get additional drivers/flags
      const { drivers, flags: baseFlags } = computeDriversFlags(
        totalUsd, netUsd, totalCount, lastTs, now, confidence, meta.source
      );
      
      // Merge all flags
      const allFlags = [...baseFlags, ...confFlags];
      
      // ═══════════════════════════════════════════════════════════
      // PHASE 2.5: AltFlow Integrity Gate
      // ═══════════════════════════════════════════════════════════
      
      // NaN/Inf guard: if any core metric is invalid, skip row entirely
      if (!Number.isFinite(totalUsd) || !Number.isFinite(netUsd) || !Number.isFinite(score)) {
        allFlags.push({ code: 'CALC_ERROR', severity: 'CRITICAL', detail: 'NaN/Inf in core metrics' });
        continue; // Skip this row entirely
      }
      
      // Min evidence policy
      let finalConfidence = confidence;
      const MIN_EVIDENCE = window === '24h' 
        ? { trades: 5, spanHours: 2 }
        : { trades: 15, spanHours: 12 };
      
      if (totalCount < MIN_EVIDENCE.trades || spanHours < MIN_EVIDENCE.spanHours) {
        finalConfidence = Math.min(finalConfidence, 0.35); // Cap below strong-only threshold
        allFlags.push({ 
          code: 'LOW_EVIDENCE', 
          severity: 'WARN', 
          detail: `trades=${totalCount}/${MIN_EVIDENCE.trades} span=${spanHours.toFixed(1)}h/${MIN_EVIDENCE.spanHours}h`,
        });
      }
      
      // Strong-only gate: confidence must be >= 0.55 AND no critical flags
      const hasCritical = allFlags.some(f => f.severity === 'CRITICAL');
      const passesStrongOnly = finalConfidence >= 0.55 && !hasCritical;
      
      totalConfidence += finalConfidence;
      
      rows.push({
        chainId,
        tokenAddress,
        tokenSymbol,
        buyUsd,
        sellUsd,
        netUsd,
        totalUsd,
        buySellRatio,
        score,
        confidence: finalConfidence,
        side,
        passesStrongOnly, // PHASE 2.5: strong-only gate result
        // STEP 3: Enhanced fields
        quality: {
          priceSource,
          priceConfidence: null,
          poolStatus: 'UNKNOWN' as PoolStatus,
          poolScore: 50,
        },
        evidence: {
          trades: totalCount,
          uniquePools,
          spanHours,
          pricedShare,
          pricedCount,
        },
        components: {
          dexNetUsd: netUsd,
          cexNetUsd: 0,
          whaleNetUsd: 0,
        },
        drivers,
        flags: allFlags,
        lastTs,
        totalCount,
      });
    }
    
    // Sort by absolute score deviation from 50 (strongest signals first)
    rows.sort((a, b) => Math.abs(b.score - 50) - Math.abs(a.score - 50));
    
    return {
      ok: true,
      window,
      chainId,
      updatedAt: now,
      rows,
      meta: {
        tokenCount: rows.length,
        labelsCoverage: rows.length > 0 ? labeledCount / rows.length : 0,
        avgConfidence: rows.length > 0 ? totalConfidence / rows.length : 0,
      },
    };
  }
  
  /**
   * Compute and persist to legacy AltFlowPointModel for backward compatibility
   */
  async computeAndPersist(window: AltflowWindow, chainId: number): Promise<AltflowResult> {
    const result = await this.compute(window, chainId);
    
    // Persist to legacy model for backward compat
    if (result.rows.length > 0) {
      const ops = result.rows.map(r => ({
        updateOne: {
          filter: { chainId, window, symbol: r.tokenSymbol, t: result.updatedAt },
          update: {
            $set: {
              chainId,
              t: result.updatedAt,
              window,
              symbol: r.tokenSymbol,
              score: (r.score - 50) / 50, // Convert 0-100 to -1..1 for legacy
              confidence: r.confidence,
              drivers: r.drivers,
              flags: r.flags,
              cexNetUsd: r.components.cexNetUsd,
              dexNetUsd: r.components.dexNetUsd,
              whaleUsd: r.components.whaleNetUsd,
              // PHASE 2.2: Persist quality/evidence/modelFeatures
              quality: r.quality,
              evidence: r.evidence,
              modelFeatures: {
                poolScore: r.quality.poolScore,
                poolStatus: r.quality.poolStatus,
                tvlUsd: null, // TODO: integrate from TVL job
                priceReliability: r.quality.priceConfidence,
                usdSource: r.quality.priceSource,
                pricedShare: r.evidence.pricedShare,
                evidenceCount: r.evidence.trades,
              },
            },
          },
          upsert: true,
        },
      }));
      
      try {
        await AltFlowPointModel.bulkWrite(ops, { ordered: false });
      } catch (e) {
        console.error('[AltflowAggregate] Legacy persist error:', e);
      }
    }
    
    return result;
  }
  
  /**
   * Get latest computed result
   */
  async getLatest(window: AltflowWindow, chainId: number): Promise<AltflowResult | null> {
    // Compute fresh (no caching for now - data is fast enough)
    return this.compute(window, chainId);
  }
  
  /**
   * Format for API response (split into accumulation/distribution)
   * STEP 3: Include quality, evidence, components
   */
  formatForApi(result: AltflowResult) {
    const mapRow = (r: AltflowRankingRow) => ({
      symbol: r.tokenSymbol,
      address: r.tokenAddress,
      chainId: r.chainId,
      score: r.score,
      side: r.side,
      confidence: r.confidence,
      // STEP 3: Enhanced fields
      quality: r.quality,
      evidence: r.evidence,
      components: r.components,
      drivers: r.drivers,
      flags: r.flags,
      totalUsd: r.totalUsd,
      buyUsd: r.buyUsd,
      sellUsd: r.sellUsd,
    });
    
    const topAccumulation = result.rows
      .filter(r => r.side === 'ACCUMULATION')
      .slice(0, 10)
      .map(mapRow);
    
    const topDistribution = result.rows
      .filter(r => r.side === 'DISTRIBUTION')
      .slice(0, 10)
      .map(mapRow);
    
    return {
      ok: true,
      window: result.window,
      chainId: result.chainId,
      generatedAt: result.updatedAt,
      topAccumulation,
      topDistribution,
      totalTokens: result.rows.length,
      meta: result.meta,
    };
  }
}

// Singleton
export const altflowAggregateService = new AltflowAggregateService();

console.log('[OnChain V2] AltFlow Aggregate Service v2 loaded');
