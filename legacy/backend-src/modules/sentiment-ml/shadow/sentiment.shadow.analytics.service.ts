/**
 * Sentiment Shadow Analytics Service
 * ====================================
 * 
 * BLOCK 9: Computes hit rates and edge for Rule vs ML.
 * 
 * Key metrics:
 * - ruleHitRate: % of correct Rule predictions
 * - mlHitRate: % of correct ML predictions
 * - delta: mlHitRate - ruleHitRate
 * - agreementRate: % of matching decisions
 * - disagreementPerformance: who wins when they disagree
 * 
 * Promotion trigger:
 * - samples >= 150
 * - delta >= 0.05 (ML +5%)
 * - mlHitRate > 0.55
 */

import { getSentimentShadowDecisionModel, SentimentShadowDecision } from './sentiment.shadow.model.js';
import { getSentimentPriceAdapter } from '../dataset/sentiment-price.adapter.js';

// ── Adaptive Labeling Constants (TASK 2.1+) ──
const VOLATILITY_K = 0.8;           // key coefficient: threshold = k * volatility
const MIN_THRESHOLD = 0.003;        // 0.3% floor
const MAX_THRESHOLD = 0.03;         // 3% ceiling
const VOLATILITY_LOW = 0.005;       // <0.5% daily vol = LOW
const VOLATILITY_MED = 0.015;       // <1.5% daily vol = MED, else HIGH
const LOOKBACK_BARS_24H = 14;       // 14 daily bars for 24H horizon vol
const LOOKBACK_BARS_7D = 8;         // 8 weekly-equivalent bars for 7D horizon

export interface ShadowSummary {
  total: number;
  evaluated: number;
  pending: number;
  
  ruleHitRate: number;
  mlHitRate: number;
  delta: number;
  
  agreementRate: number;
  
  ruleWins: number;
  mlWins: number;
  neutral: number;
  
  // Disagreement analysis
  disagreements: number;
  mlWinsOnDisagreement: number;
  ruleWinsOnDisagreement: number;
  
  // Promotion readiness
  readyForPromotion: boolean;
  promotionBlockers: string[];
}

export interface DisagreementDetail {
  symbol: string;
  asOf: Date;
  ruleAction: string;
  mlAction: string;
  forwardReturn: number;
  winner: 'RULE' | 'ML' | 'TIE';
}

export interface CrossSliceResult {
  slice: string;
  importance: string;
  eventType: string;
  recency: string;
  samples: number;
  ruleHitRate: number;
  mlHitRate: number;
  delta: number;
  avgConfidence: number;
  avgReturnPct: number;
}

export class SentimentShadowAnalyticsService {
  private priceAdapter = getSentimentPriceAdapter();

  /**
   * Finalize a single shadow decision with adaptive volatility-based labeling.
   * 
   * TASK 2.1+: Instead of fixed ±0.3% thresholds, we compute:
   *   threshold = clamp(k * volatility, 0.3%, 3%)
   * where volatility = stdDev(recent daily returns).
   * 
   * This prevents:
   *   - BTC flooding NEUTRAL (low vol → low threshold)
   *   - ALTs flooding UP/DOWN (high vol → high threshold)
   */
  async finalizeDecision(decisionId: string): Promise<{
    success: boolean;
    error?: string;
  }> {
    const ShadowModel = getSentimentShadowDecisionModel();
    const decision = await ShadowModel.findById(decisionId);
    
    if (!decision) {
      return { success: false, error: 'Decision not found' };
    }

    if (decision.evaluated) {
      return { success: true }; // Already done
    }

    // ── Step 1: Get entry price ──
    const entryPrice = await this.priceAdapter.getClosePriceAt(
      decision.symbol,
      decision.asOf
    );

    if (!entryPrice) {
      return { success: false, error: 'Entry price not found' };
    }

    // ── Step 2: Get exit price (horizon-aware) ──
    const horizonMs = decision.window === '24H'
      ? 24 * 60 * 60 * 1000
      : 7 * 24 * 60 * 60 * 1000;
    const exitTime = new Date(decision.asOf.getTime() + horizonMs);
    const exitPrice = await this.priceAdapter.getClosePriceAt(
      decision.symbol,
      exitTime
    );

    if (!exitPrice) {
      return { success: false, error: 'Exit price not found' };
    }

    // ── Step 3: Calculate raw forward return ──
    const forwardReturn = (exitPrice.price - entryPrice.price) / entryPrice.price;
    const forwardReturnPct = forwardReturn * 100; // e.g. 1.5 means +1.5%

    // ── Step 4: Compute adaptive volatility for this symbol/horizon ──
    const volatility = await this.computeVolatility(decision.symbol, decision.asOf, decision.window);
    const volatilityBucket = this.getVolatilityBucket(volatility);
    
    // ── Step 5: Adaptive threshold ──
    const rawThreshold = VOLATILITY_K * volatility;
    const adaptiveThreshold = Math.max(MIN_THRESHOLD, Math.min(MAX_THRESHOLD, rawThreshold));

    // ── Step 6: Label with adaptive threshold ──
    let forwardLabel: 'UP' | 'DOWN' | 'FLAT' = 'FLAT';
    if (forwardReturn > adaptiveThreshold) forwardLabel = 'UP';
    else if (forwardReturn < -adaptiveThreshold) forwardLabel = 'DOWN';

    // ── Step 7: Determine correctness ──
    const ruleCorrect = this.isCorrect(decision.ruleAction, forwardLabel);
    const mlCorrect = this.isCorrect(decision.mlAction, forwardLabel);

    // ── Step 8: Update decision with all fields ──
    decision.forwardReturn = forwardReturn;
    decision.forwardReturnPct = forwardReturnPct;
    decision.forwardLabel = forwardLabel;
    decision.volatility = volatility;
    decision.volatilityBucket = volatilityBucket;
    decision.adaptiveThreshold = adaptiveThreshold;
    decision.ruleCorrect = ruleCorrect;
    decision.mlCorrect = mlCorrect;
    decision.evaluated = true;

    await decision.save();

    console.log(
      `[Shadow] Finalized ${decision.symbol} | Return:${forwardReturnPct.toFixed(2)}% | ` +
      `Vol:${(volatility * 100).toFixed(2)}%(${volatilityBucket}) | ` +
      `Thresh:±${(adaptiveThreshold * 100).toFixed(2)}% | ` +
      `Label:${forwardLabel} | Rule:${ruleCorrect ? '✓' : '✗'} ML:${mlCorrect ? '✓' : '✗'}`
    );

    return { success: true };
  }

  /**
   * Compute realized volatility for a symbol using stdDev of recent daily returns.
   * Horizon-aware: 24H uses daily bars, 7D uses wider lookback.
   */
  private async computeVolatility(symbol: string, asOf: Date, window: string): Promise<number> {
    const lookbackBars = window === '7D' ? LOOKBACK_BARS_7D : LOOKBACK_BARS_24H;
    const lookbackMs = lookbackBars * 24 * 60 * 60 * 1000;
    
    const fromDate = new Date(asOf.getTime() - lookbackMs);
    
    try {
      // Fetch daily bars for volatility calculation
      let querySymbol = symbol.toUpperCase();
      if (!querySymbol.endsWith('USDT')) querySymbol = `${querySymbol}USDT`;

      const { getDirPriceAdapter } = await import('../../exchange-ml/dir/ports/dir.price.adapter.js');
      const adapter = getDirPriceAdapter();
      
      const bars = await adapter.getSeries({
        symbol: querySymbol,
        from: Math.floor(fromDate.getTime() / 1000),
        to: Math.floor(asOf.getTime() / 1000),
        tf: '1d',
      });

      if (bars.length < 3) {
        // Fallback: try hourly bars
        const hourlyBars = await adapter.getSeries({
          symbol: querySymbol,
          from: Math.floor(fromDate.getTime() / 1000),
          to: Math.floor(asOf.getTime() / 1000),
          tf: '1h',
        });
        
        if (hourlyBars.length < 5) {
          console.warn(`[Shadow] Not enough bars for ${symbol} vol, using default`);
          return 0.01; // 1% default fallback
        }
        
        return this.calcStdDevReturns(hourlyBars.map(b => b.close));
      }

      return this.calcStdDevReturns(bars.map(b => b.close));
    } catch (err: any) {
      console.warn(`[Shadow] computeVolatility(${symbol}) error:`, err.message);
      return 0.01; // safe fallback
    }
  }

  /**
   * Standard deviation of log returns from a price series.
   */
  private calcStdDevReturns(prices: number[]): number {
    if (prices.length < 2) return 0.01;
    
    const returns: number[] = [];
    for (let i = 1; i < prices.length; i++) {
      if (prices[i - 1] > 0) {
        returns.push((prices[i] - prices[i - 1]) / prices[i - 1]);
      }
    }
    
    if (returns.length === 0) return 0.01;
    
    const mean = returns.reduce((s, r) => s + r, 0) / returns.length;
    const variance = returns.reduce((s, r) => s + (r - mean) ** 2, 0) / returns.length;
    return Math.sqrt(variance);
  }

  /**
   * Map raw volatility to bucket.
   */
  private getVolatilityBucket(vol: number): 'LOW' | 'MED' | 'HIGH' {
    if (vol < VOLATILITY_LOW) return 'LOW';
    if (vol < VOLATILITY_MED) return 'MED';
    return 'HIGH';
  }

  /**
   * Finalize all pending decisions
   */
  async finalizeAllPending(): Promise<{
    processed: number;
    success: number;
    failed: number;
  }> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const cutoff = new Date();
    cutoff.setHours(cutoff.getHours() - 26); // 24H + 2H grace
    
    const pending = await ShadowModel.find({
      evaluated: false,
      asOf: { $lte: cutoff },
    }).limit(200);

    let success = 0;
    let failed = 0;

    for (const decision of pending) {
      const result = await this.finalizeDecision(decision._id.toString());
      if (result.success) {
        success++;
      } else {
        failed++;
      }
    }

    return {
      processed: pending.length,
      success,
      failed,
    };
  }

  /**
   * Get full summary of shadow performance
   */
  async getSummary(): Promise<ShadowSummary> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const [total, evaluated] = await Promise.all([
      ShadowModel.countDocuments(),
      ShadowModel.countDocuments({ evaluated: true }),
    ]);

    // Get evaluated decisions for analysis
    const decisions = await ShadowModel.find({ evaluated: true }).lean();

    const ruleWins = decisions.filter(d => d.ruleCorrect).length;
    const mlWins = decisions.filter(d => d.mlCorrect).length;
    const neutral = decisions.filter(d => d.forwardLabel === 'FLAT').length;

    const ruleHitRate = evaluated > 0 ? ruleWins / evaluated : 0;
    const mlHitRate = evaluated > 0 ? mlWins / evaluated : 0;
    const delta = mlHitRate - ruleHitRate;

    // Agreement analysis
    const agreements = decisions.filter(d => d.agreement).length;
    const agreementRate = decisions.length > 0 ? agreements / decisions.length : 0;

    // Disagreement analysis
    const disagreements = decisions.filter(d => !d.agreement);
    const mlWinsOnDisagreement = disagreements.filter(d => d.mlCorrect && !d.ruleCorrect).length;
    const ruleWinsOnDisagreement = disagreements.filter(d => d.ruleCorrect && !d.mlCorrect).length;

    // Promotion readiness check
    const blockers: string[] = [];
    if (evaluated < 150) blockers.push(`Need 150 samples, have ${evaluated}`);
    if (delta < 0.05) blockers.push(`Delta ${(delta * 100).toFixed(1)}% < 5%`);
    if (mlHitRate < 0.55) blockers.push(`ML hit rate ${(mlHitRate * 100).toFixed(1)}% < 55%`);

    return {
      total,
      evaluated,
      pending: total - evaluated,
      
      ruleHitRate,
      mlHitRate,
      delta,
      
      agreementRate,
      
      ruleWins,
      mlWins,
      neutral,
      
      disagreements: disagreements.length,
      mlWinsOnDisagreement,
      ruleWinsOnDisagreement,
      
      readyForPromotion: blockers.length === 0,
      promotionBlockers: blockers,
    };
  }

  /**
   * Get disagreement details for analysis
   */
  async getDisagreements(limit: number = 50): Promise<DisagreementDetail[]> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const disagreements = await ShadowModel.find({
      evaluated: true,
      agreement: false,
    })
      .sort({ asOf: -1 })
      .limit(limit)
      .lean();

    return disagreements.map(d => ({
      symbol: d.symbol,
      asOf: d.asOf,
      ruleAction: d.ruleAction,
      mlAction: d.mlAction,
      forwardReturn: d.forwardReturn || 0,
      winner: this.determineWinner(d),
    }));
  }

  /**
   * Get per-symbol breakdown
   */
  async getSymbolBreakdown(): Promise<Array<{
    symbol: string;
    samples: number;
    ruleHitRate: number;
    mlHitRate: number;
    delta: number;
  }>> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const pipeline = [
      { $match: { evaluated: true } },
      { $group: {
        _id: '$symbol',
        samples: { $sum: 1 },
        ruleWins: { $sum: { $cond: ['$ruleCorrect', 1, 0] } },
        mlWins: { $sum: { $cond: ['$mlCorrect', 1, 0] } },
      }},
      { $sort: { samples: -1 } },
    ];

    const results = await ShadowModel.aggregate(pipeline);

    return results.map(r => ({
      symbol: r._id,
      samples: r.samples,
      ruleHitRate: r.samples > 0 ? r.ruleWins / r.samples : 0,
      mlHitRate: r.samples > 0 ? r.mlWins / r.samples : 0,
      delta: r.samples > 0 ? (r.mlWins - r.ruleWins) / r.samples : 0,
    }));
  }

  /**
   * TASK 2.0: Slice analytics by news context dimension
   */
  async getSliceBreakdown(dimension: 'eventType' | 'importanceBand' | 'assetClass' | 'recencyBucket'): Promise<Array<{
    value: string;
    samples: number;
    ruleHitRate: number;
    mlHitRate: number;
    delta: number;
  }>> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const fieldPath = `$newsContext.${dimension}`;
    
    const pipeline = [
      { $match: { evaluated: true, [`newsContext.${dimension}`]: { $exists: true, $ne: null } } },
      { $group: {
        _id: fieldPath,
        samples: { $sum: 1 },
        ruleWins: { $sum: { $cond: ['$ruleCorrect', 1, 0] } },
        mlWins: { $sum: { $cond: ['$mlCorrect', 1, 0] } },
      }},
      { $sort: { samples: -1 } },
    ];

    const results = await ShadowModel.aggregate(pipeline);

    return results.map(r => ({
      value: r._id || 'unknown',
      samples: r.samples,
      ruleHitRate: r.samples > 0 ? r.ruleWins / r.samples : 0,
      mlHitRate: r.samples > 0 ? r.mlWins / r.samples : 0,
      delta: r.samples > 0 ? (r.mlWins - r.ruleWins) / r.samples : 0,
    }));
  }

  /**
   * TASK 2.0: Confidence calibration analysis
   */
  async getConfidenceCalibration(bucketSize: number = 0.1): Promise<Array<{
    confidenceRange: string;
    samples: number;
    mlAccuracy: number;
  }>> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const decisions = await ShadowModel.find({ evaluated: true }).lean();
    
    // Use fixed buckets: 0-0.4, 0.4-0.6, 0.6-0.8, 0.8+
    const CONFIDENCE_BUCKETS = [
      { label: '0.0-0.4', min: 0, max: 0.4 },
      { label: '0.4-0.6', min: 0.4, max: 0.6 },
      { label: '0.6-0.8', min: 0.6, max: 0.8 },
      { label: '0.8+', min: 0.8, max: 1.1 },
    ];

    return CONFIDENCE_BUCKETS.map(bucket => {
      const inBucket = decisions.filter(d => {
        const conf = d.mlConfidence || 0;
        return conf >= bucket.min && conf < bucket.max;
      });
      const correct = inBucket.filter(d => d.mlCorrect).length;
      return {
        confidenceRange: bucket.label,
        samples: inBucket.length,
        mlAccuracy: inBucket.length > 0 ? correct / inBucket.length : 0,
      };
    }).filter(b => b.samples > 0);
  }

  /**
   * Cross-slice analysis: combinations of importance + eventType + recency
   * Returns top winning and losing ML slices sorted by delta.
   */
  async getCrossSliceAnalysis(minSamples: number = 3): Promise<{
    topWinning: CrossSliceResult[];
    topLosing: CrossSliceResult[];
    allSlices: CrossSliceResult[];
  }> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const pipeline = [
      { $match: { evaluated: true, 'newsContext': { $exists: true, $ne: null } } },
      { $group: {
        _id: {
          importance: '$newsContext.importanceBand',
          eventType: '$newsContext.eventType',
          recency: '$newsContext.recencyBucket',
        },
        samples: { $sum: 1 },
        ruleWins: { $sum: { $cond: ['$ruleCorrect', 1, 0] } },
        mlWins: { $sum: { $cond: ['$mlCorrect', 1, 0] } },
        avgConfidence: { $avg: '$mlConfidence' },
        avgReturnPct: { $avg: '$forwardReturnPct' },
      }},
      { $match: { samples: { $gte: minSamples } } },
      { $sort: { samples: -1 } },
    ];

    const results = await ShadowModel.aggregate(pipeline);

    const allSlices: CrossSliceResult[] = results.map(r => {
      const ruleHitRate = r.samples > 0 ? r.ruleWins / r.samples : 0;
      const mlHitRate = r.samples > 0 ? r.mlWins / r.samples : 0;
      return {
        slice: `${r._id.importance || '?'} + ${r._id.eventType || '?'} + ${r._id.recency || '?'}`,
        importance: r._id.importance,
        eventType: r._id.eventType,
        recency: r._id.recency,
        samples: r.samples,
        ruleHitRate,
        mlHitRate,
        delta: mlHitRate - ruleHitRate,
        avgConfidence: +(r.avgConfidence || 0).toFixed(3),
        avgReturnPct: +(r.avgReturnPct || 0).toFixed(2),
      };
    });

    const sorted = [...allSlices].sort((a, b) => b.delta - a.delta);

    return {
      topWinning: sorted.filter(s => s.delta > 0).slice(0, 5),
      topLosing: sorted.filter(s => s.delta < 0).slice(0, 5).reverse(),
      allSlices,
    };
  }

  /**
   * Check if action was correct given the outcome
   */
  private isCorrect(action: string, label: 'UP' | 'DOWN' | 'FLAT'): boolean {
    if (label === 'FLAT') return action === 'NEUTRAL';
    if (action === 'LONG' && label === 'UP') return true;
    if (action === 'SHORT' && label === 'DOWN') return true;
    return false;
  }

  /**
   * Determine winner when Rule and ML disagree
   */
  private determineWinner(d: SentimentShadowDecision): 'RULE' | 'ML' | 'TIE' {
    if (d.ruleCorrect && !d.mlCorrect) return 'RULE';
    if (d.mlCorrect && !d.ruleCorrect) return 'ML';
    return 'TIE';
  }
}

// Singleton
let analyticsInstance: SentimentShadowAnalyticsService | null = null;

export function getSentimentShadowAnalyticsService(): SentimentShadowAnalyticsService {
  if (!analyticsInstance) {
    analyticsInstance = new SentimentShadowAnalyticsService();
  }
  return analyticsInstance;
}

console.log('[Sentiment-ML] Shadow Analytics Service loaded (BLOCK 9)');
