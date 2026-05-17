/**
 * Sentiment Aggregation Service
 * =============================
 * 
 * BLOCK 4: Агрегация sentiment events по символам и временным окнам
 * 
 * Принцип:
 * - Weighted average: Σ(weightedCentered) / Σ(|weight|)
 * - Windows: 24H, 7D, 30D
 * - Deterministic mapping to forecast
 * - Production-ready aggregation
 */

import { SentimentEventModel, ISentimentEvent } from '../storage/sentiment-event.model.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';

export type WindowKey = '24H' | '7D' | '30D';

// Window durations in milliseconds
const WINDOW_MS: Record<WindowKey, number> = {
  '24H': 24 * 60 * 60 * 1000,
  '7D': 7 * 24 * 60 * 60 * 1000,
  '30D': 30 * 24 * 60 * 60 * 1000,
};

// Expected return multipliers (conservative v1)
const RETURN_K: Record<WindowKey, number> = {
  '24H': 0.006,  // 0.6% max
  '7D': 0.02,    // 2% max
  '30D': 0.06,   // 6% max
};

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

export interface AggregationResult {
  symbol: string;
  window: WindowKey;
  asOf?: Date;
  score: number;
  bias: number;
  confidence: number;
  eventsCount: number;
  uniqueAuthors: number;
  posCount: number;
  negCount: number;
  neuCount: number;
  topAuthors: Array<{
    handle: string;
    weight: number;
    avgScore: number;
    influence: number;
    authorScore: number;
  }>;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  expectedReturnPct: number;
  // ML Features (BLOCK 3)
  authorScoreMean?: number;
  influenceMean?: number;
  botProbMean?: number;
  weightedScore?: number;
  weightedConfidence?: number;
}

export class SentimentAggregationService {
  /**
   * Compute aggregation for a symbol across all windows
   */
  async computeForSymbol(
    symbol: string, 
    now = new Date(), 
    windows: WindowKey[] = ['24H', '7D', '30D']
  ): Promise<AggregationResult[]> {
    const results: AggregationResult[] = [];
    
    for (const window of windows) {
      const from = new Date(now.getTime() - WINDOW_MS[window]);
      
      // Fetch events for this symbol and window
      const events = await SentimentEventModel.find({
        symbol: symbol.toUpperCase(),
        tweetCreatedAt: { $gte: from, $lte: now },
      })
        .select('authorHandle baseLabel baseScore weightedScore weightedConfidence authorScore influence botProb')
        .lean();

      // Aggregate
      const agg = this.aggregate(events as any[], symbol, window);
      
      // Save to DB
      await SentimentAggregateModel.create({
        symbol: symbol.toUpperCase(),
        window,
        asOf: now,
        score: agg.score,
        bias: agg.bias,
        confidence: agg.confidence,
        eventsCount: agg.eventsCount,
        uniqueAuthors: agg.uniqueAuthors,
        posCount: agg.posCount,
        negCount: agg.negCount,
        neuCount: agg.neuCount,
        topAuthors: agg.topAuthors,
        direction: agg.direction,
        expectedReturnPct: agg.expectedReturnPct,
        // ML Features (BLOCK 3)
        authorScoreMean: agg.authorScoreMean,
        influenceMean: agg.influenceMean,
        botProbMean: agg.botProbMean,
        weightedScore: agg.weightedScore,
        weightedConfidence: agg.weightedConfidence,
      });

      results.push(agg);
    }
    
    return results;
  }

  /**
   * Core aggregation logic
   */
  private aggregate(
    events: Array<{
      authorHandle?: string;
      baseLabel?: string;
      baseScore?: number;
      weightedScore?: number;
      weightedConfidence?: number;
      authorScore?: number;
      influence?: number;
    }>,
    symbol: string,
    window: WindowKey
  ): AggregationResult {
    // Empty case
    if (!events.length) {
      return {
        symbol: symbol.toUpperCase(),
        window,
        score: 0.5,
        bias: 0,
        confidence: 0,
        eventsCount: 0,
        uniqueAuthors: 0,
        posCount: 0,
        negCount: 0,
        neuCount: 0,
        topAuthors: [],
        direction: 'NEUTRAL',
        expectedReturnPct: 0,
      };
    }

    let weightSum = 0;
    let centeredSum = 0;  // weighted centered scores
    let confSum = 0;      // weighted confidences
    
    let posCount = 0;
    let negCount = 0;
    let neuCount = 0;

    // Track authors
    const authorMap = new Map<string, {
      weight: number;
      scoreSum: number;
      count: number;
      influence: number;
      authorScore: number;
    }>();

    for (const e of events) {
      // Use weighted score if available, fallback to base
      const score = clamp01(e.weightedScore ?? e.baseScore ?? 0.5);
      const centered = (score - 0.5) * 2; // [-1..+1]
      
      // Use confidence as weight (simple v1)
      const conf = clamp01(e.weightedConfidence ?? 0.5);
      const weight = Math.max(0.1, conf); // minimum weight 0.1
      
      weightSum += weight;
      centeredSum += centered * weight;
      confSum += conf * weight;

      // Count by label
      if (e.baseLabel === 'POSITIVE') posCount++;
      else if (e.baseLabel === 'NEGATIVE') negCount++;
      else neuCount++;

      // Track author contributions
      const handle = e.authorHandle || 'unknown';
      const existing = authorMap.get(handle) || {
        weight: 0,
        scoreSum: 0,
        count: 0,
        influence: clamp01(e.influence ?? 0.5),
        authorScore: clamp01(e.authorScore ?? 0.5),
      };
      
      existing.weight += weight;
      existing.scoreSum += score * weight;
      existing.count++;
      existing.influence = Math.max(existing.influence, clamp01(e.influence ?? 0.5));
      existing.authorScore = Math.max(existing.authorScore, clamp01(e.authorScore ?? 0.5));
      
      authorMap.set(handle, existing);
    }

    // Calculate final metrics
    const bias = weightSum > 0 ? centeredSum / weightSum : 0;  // [-1..+1]
    const score = clamp01(bias / 2 + 0.5);                      // [0..1]
    const confidence = weightSum > 0 ? clamp01(confSum / weightSum) : 0;

    // Calculate enrichment means for ML features
    const authorScoreMean = events.length > 0
      ? events.reduce((sum, e) => sum + clamp01(e.authorScore ?? 0.5), 0) / events.length
      : 0.5;
    const influenceMean = events.length > 0
      ? events.reduce((sum, e) => sum + clamp01(e.influence ?? 0.5), 0) / events.length
      : 0.5;
    const botProbMean = events.length > 0
      ? events.reduce((sum, e) => sum + clamp01(e.botProb ?? 0.5), 0) / events.length
      : 0.5;
    const weightedScoreMean = events.length > 0
      ? events.reduce((sum, e) => sum + clamp01(e.weightedScore ?? e.baseScore ?? 0.5), 0) / events.length
      : 0.5;
    const weightedConfidenceMean = events.length > 0
      ? events.reduce((sum, e) => sum + clamp01(e.weightedConfidence ?? 0.5), 0) / events.length
      : 0.5;

    // Top 5 authors by weight
    const topAuthors = [...authorMap.entries()]
      .map(([handle, data]) => ({
        handle,
        weight: data.weight,
        avgScore: data.weight > 0 ? data.scoreSum / data.weight : 0.5,
        influence: data.influence,
        authorScore: data.authorScore,
      }))
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 5);

    // Map to forecast
    const direction = bias > 0.1 ? 'LONG' : bias < -0.1 ? 'SHORT' : 'NEUTRAL';
    const expectedReturnPct = bias * RETURN_K[window];

    return {
      symbol: symbol.toUpperCase(),
      window,
      score,
      bias,
      confidence,
      eventsCount: events.length,
      uniqueAuthors: authorMap.size,
      posCount,
      negCount,
      neuCount,
      topAuthors,
      direction,
      expectedReturnPct,
      // ML enrichment means
      authorScoreMean,
      influenceMean,
      botProbMean,
      weightedScore: weightedScoreMean,
      weightedConfidence: weightedConfidenceMean,
    };
  }

  /**
   * Get latest aggregate for symbol and window
   */
  async getLatest(symbol: string, window: WindowKey): Promise<AggregationResult | null> {
    const doc = await SentimentAggregateModel.findOne({
      symbol: symbol.toUpperCase(),
      window,
    })
      .sort({ asOf: -1 })
      .lean();

    if (!doc) return null;

    return {
      symbol: doc.symbol,
      window: doc.window as WindowKey,
      asOf: doc.asOf,
      score: doc.score,
      bias: doc.bias,
      confidence: doc.confidence,
      eventsCount: doc.eventsCount,
      uniqueAuthors: doc.uniqueAuthors,
      posCount: doc.posCount,
      negCount: doc.negCount,
      neuCount: doc.neuCount,
      topAuthors: doc.topAuthors,
      direction: doc.direction as 'LONG' | 'SHORT' | 'NEUTRAL',
      expectedReturnPct: doc.expectedReturnPct,
      weightedScore: doc.weightedScore,
      weightedConfidence: doc.weightedConfidence,
      authorScoreMean: doc.authorScoreMean,
      influenceMean: doc.influenceMean,
      botProbMean: doc.botProbMean,
    };
  }

  /**
   * Get time series for chart
   */
  async getSeries(
    symbol: string, 
    window: WindowKey, 
    days = 30
  ): Promise<Array<{
    t: Date;
    score: number;
    confidence: number;
    bias: number;
  }>> {
    const from = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

    const docs = await SentimentAggregateModel.find({
      symbol: symbol.toUpperCase(),
      window,
      asOf: { $gte: from },
    })
      .sort({ asOf: 1 })
      .select('asOf score confidence bias')
      .lean();

    return docs.map(d => ({
      t: d.asOf,
      score: d.score,
      confidence: d.confidence,
      bias: d.bias,
    }));
  }
}

// Singleton instance
export const sentimentAggregationService = new SentimentAggregationService();
