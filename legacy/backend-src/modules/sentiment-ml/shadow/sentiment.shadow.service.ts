/**
 * Sentiment Shadow Service
 * =========================
 * 
 * BLOCK 9: Records shadow decisions (Rule vs ML).
 * 
 * Called from aggregate pipeline to record both decisions
 * without affecting production verdict.
 * 
 * Flow:
 * 1. Aggregate is computed (rule-based)
 * 2. ML inference runs in parallel
 * 3. Both decisions are recorded in shadow collection
 * 4. Only rule decision is returned to user
 */

import { getSentimentShadowDecisionModel, SentimentShadowDecision } from './sentiment.shadow.model.js';
import { SentimentBinaryInferenceService } from '../binary/sentiment.binary.inference.service.js';

export interface RecordShadowParams {
  symbol: string;
  asOf: Date;
  
  // Rule decision
  ruleAction: 'LONG' | 'SHORT' | 'NEUTRAL';
  ruleConfidence: number;
  ruleBias: number;
  
  // Aggregate data for ML
  score: number;
  weightedScore: number;
  weightedConfidence: number;
  eventsCount: number;
  authorScoreMean?: number;
  influenceMean?: number;
  botProbMean?: number;
}

export class SentimentShadowService {
  /**
   * Record a shadow decision comparing Rule vs ML
   */
  async recordShadowDecision(params: RecordShadowParams): Promise<{
    recorded: boolean;
    agreement: boolean;
    error?: string;
  }> {
    const { 
      symbol, asOf, 
      ruleAction, ruleConfidence, ruleBias,
      score, weightedScore, weightedConfidence, eventsCount,
      authorScoreMean = 0, influenceMean = 0, botProbMean = 0,
    } = params;

    try {
      // Run ML inference for 24H
      const mlResult = await SentimentBinaryInferenceService.infer({
        window: '24H',
        sampleLike: {
          symbol,
          asOf,
          bias: ruleBias,
          score,
          weightedScore,
          weightedConfidence,
          eventsCount,
          authorScoreMean,
          influenceMean,
          botProbMean,
        },
      });

      const agreement = ruleAction === mlResult.action;

      // ── TASK 2.0: Fetch news context for this symbol ──
      const newsContext = await this.fetchNewsContext(symbol);

      const ShadowModel = getSentimentShadowDecisionModel();
      
      await ShadowModel.create({
        symbol,
        asOf,
        window: '24H',
        
        ruleAction,
        ruleConfidence,
        ruleBias,
        
        mlAction: mlResult.action,
        mlConfidence: mlResult.confidence,
        mlProbabilityUp: mlResult.pUp,
        mlModelId: mlResult.meta.modelId,
        
        agreement,
        evaluated: false,
        newsContext,
      });

      console.log(`[Shadow] Recorded ${symbol} | Rule:${ruleAction} ML:${mlResult.action} | Agree:${agreement} | ctx:${newsContext?.eventType || '-'}`);

      return { recorded: true, agreement };

    } catch (err: any) {
      // Duplicate key error - already recorded
      if (err.code === 11000) {
        return { recorded: false, agreement: false, error: 'duplicate' };
      }

      console.error(`[Shadow] Error recording ${symbol}:`, err.message);
      return { recorded: false, agreement: false, error: err.message };
    }
  }

  /**
   * TASK 2.0: Fetch top news cluster context for a symbol.
   * Uses the news feed API since clusters are computed on-the-fly (not stored in DB).
   */
  private async fetchNewsContext(symbol: string): Promise<{
    eventType: string;
    importanceBand: string;
    sourcesCount: number;
    isBreaking: boolean;
    clusterSize: number;
    recencyBucket: string;
    assetClass: string;
    topClusterTitle: string;
  } | undefined> {
    try {
      const assetSymbol = symbol.replace(/USDT$/i, '');
      
      // Import pipeline to get fresh clusters
      const { newsIntelligencePipeline } = await import('../../news-intelligence/pipeline.service.js');
      const result = await newsIntelligencePipeline.buildFeed({ limit: 50, hoursBack: 48 });
      
      if (!result?.clusters?.length) {
        console.warn(`[Shadow] fetchNewsContext(${symbol}): pipeline returned 0 clusters`);
        return undefined;
      }

      // Find cluster mentioning this asset
      const assetCluster = result.clusters.find(
        (c: any) => c.assets?.includes(assetSymbol)
      );
      
      const cluster = assetCluster || result.clusters[0]; // Fallback to top cluster
      
      return this.buildContext(cluster, assetSymbol);
    } catch (err: any) {
      console.warn(`[Shadow] fetchNewsContext(${symbol}) error:`, err.message);
      return undefined;
    }
  }

  private buildContext(cluster: any, assetSymbol: string): {
    eventType: string;
    importanceBand: string;
    sourcesCount: number;
    isBreaking: boolean;
    clusterSize: number;
    recencyBucket: string;
    assetClass: string;
    topClusterTitle: string;
  } {
    const ageMinutes = (Date.now() - new Date(cluster.firstSeenAt).getTime()) / 60000;
    let recencyBucket = '6h+';
    if (ageMinutes < 60) recencyBucket = '<1h';
    else if (ageMinutes < 180) recencyBucket = '1-3h';
    else if (ageMinutes < 360) recencyBucket = '3-6h';

    let assetClass = 'ALT';
    if (['BTC', 'BITCOIN'].includes(assetSymbol.toUpperCase())) assetClass = 'BTC';
    else if (['ETH', 'ETHEREUM'].includes(assetSymbol.toUpperCase())) assetClass = 'ETH';

    return {
      eventType: cluster.eventType || 'unknown',
      importanceBand: cluster.importanceBand || 'low',
      sourcesCount: cluster.sourcesCount || 1,
      isBreaking: cluster.isBreaking || false,
      clusterSize: Array.isArray(cluster.events) ? cluster.events.length : 1,
      recencyBucket,
      assetClass,
      topClusterTitle: (cluster.title || '').slice(0, 120),
    };
  }

  /**
   * Get pending (unevaluated) shadow decisions ready for finalization
   * A decision is ready when 24H has passed since asOf
   */
  async getPendingDecisions(limit: number = 100): Promise<SentimentShadowDecision[]> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const cutoff = new Date();
    cutoff.setHours(cutoff.getHours() - 26); // 24H + 2H grace
    
    return ShadowModel.find({
      evaluated: false,
      asOf: { $lte: cutoff },
    })
      .sort({ asOf: 1 })
      .limit(limit)
      .lean();
  }

  /**
   * Get recent shadow decisions for monitoring
   */
  async getRecentDecisions(limit: number = 50): Promise<SentimentShadowDecision[]> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    return ShadowModel.find()
      .sort({ asOf: -1 })
      .limit(limit)
      .lean();
  }

  /**
   * Get decision count stats with context coverage
   */
  async getStats(): Promise<{
    total: number;
    evaluated: number;
    pending: number;
    agreementRate: number;
    contextCoverage: number;
    contextDistribution: {
      eventTypes: Record<string, number>;
      importanceBands: Record<string, number>;
      assetClasses: Record<string, number>;
      recencyBuckets: Record<string, number>;
    };
  }> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const [total, evaluated, agreements, withContext] = await Promise.all([
      ShadowModel.countDocuments(),
      ShadowModel.countDocuments({ evaluated: true }),
      ShadowModel.countDocuments({ agreement: true }),
      ShadowModel.countDocuments({ 'newsContext.eventType': { $exists: true, $ne: null } }),
    ]);

    // Get context distribution from all decisions with newsContext
    const contextDocs = await ShadowModel.find(
      { 'newsContext.eventType': { $exists: true, $ne: null } },
      { 'newsContext': 1, '_id': 0 }
    ).lean();

    const eventTypes: Record<string, number> = {};
    const importanceBands: Record<string, number> = {};
    const assetClasses: Record<string, number> = {};
    const recencyBuckets: Record<string, number> = {};

    for (const doc of contextDocs) {
      const ctx = (doc as any).newsContext;
      if (!ctx) continue;
      if (ctx.eventType) eventTypes[ctx.eventType] = (eventTypes[ctx.eventType] || 0) + 1;
      if (ctx.importanceBand) importanceBands[ctx.importanceBand] = (importanceBands[ctx.importanceBand] || 0) + 1;
      if (ctx.assetClass) assetClasses[ctx.assetClass] = (assetClasses[ctx.assetClass] || 0) + 1;
      if (ctx.recencyBucket) recencyBuckets[ctx.recencyBucket] = (recencyBuckets[ctx.recencyBucket] || 0) + 1;
    }

    return {
      total,
      evaluated,
      pending: total - evaluated,
      agreementRate: total > 0 ? agreements / total : 0,
      contextCoverage: total > 0 ? withContext / total : 0,
      contextDistribution: { eventTypes, importanceBands, assetClasses, recencyBuckets },
    };
  }

  /**
   * TASK 2.0: Backfill newsContext for decisions that don't have it.
   * Uses current top news cluster as context snapshot.
   */
  async backfillNewsContext(): Promise<{ updated: number; failed: number; skipped: number }> {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const missing = await ShadowModel.find({
      $or: [
        { newsContext: { $exists: false } },
        { newsContext: null },
        { 'newsContext.eventType': { $exists: false } },
      ],
    }).lean();

    if (!missing.length) return { updated: 0, failed: 0, skipped: 0 };

    // Fetch current news context for each symbol
    let updated = 0;
    let failed = 0;
    let skipped = 0;

    // Group by symbol to avoid redundant pipeline calls
    const symbolGroups = new Map<string, string[]>();
    for (const dec of missing) {
      const ids = symbolGroups.get(dec.symbol) || [];
      ids.push((dec as any)._id.toString());
      symbolGroups.set(dec.symbol, ids);
    }

    for (const [symbol, ids] of symbolGroups) {
      try {
        const ctx = await this.fetchNewsContext(symbol);
        if (!ctx) {
          skipped += ids.length;
          continue;
        }
        
        await ShadowModel.updateMany(
          { _id: { $in: ids } },
          { $set: { newsContext: ctx } }
        );
        updated += ids.length;
        console.log(`[Shadow] Backfilled ${ids.length} decisions for ${symbol}: ${ctx.eventType}/${ctx.importanceBand}`);
      } catch (err: any) {
        failed += ids.length;
        console.warn(`[Shadow] Backfill failed for ${symbol}:`, err.message);
      }
    }

    return { updated, failed, skipped };
  }
}

// Singleton
let shadowServiceInstance: SentimentShadowService | null = null;

export function getSentimentShadowService(): SentimentShadowService {
  if (!shadowServiceInstance) {
    shadowServiceInstance = new SentimentShadowService();
  }
  return shadowServiceInstance;
}

console.log('[Sentiment-ML] Shadow Service loaded (BLOCK 9)');
