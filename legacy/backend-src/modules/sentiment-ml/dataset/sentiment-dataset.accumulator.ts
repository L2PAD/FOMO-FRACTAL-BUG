/**
 * Sentiment Dataset Accumulator
 * =============================
 * 
 * BLOCK 6: Forward-only dataset builder for sentiment validation.
 * 
 * Core responsibility:
 * - Find sentiment aggregates where window has closed
 * - Compute actual price return over window
 * - Create labeled samples (UP/DOWN/NEUTRAL)
 * - Atomic upsert to prevent duplicates
 * 
 * CRITICAL: No future leak — samples created only after window closes.
 * 
 * finalizeSample() statuses:
 * - CREATED: Sample successfully created
 * - SKIPPED: Not matured, empty aggregate, duplicate, or not found
 * - RETRY: Price data temporarily unavailable
 * - FAILED: Invalid data or unrecoverable error
 */

import { SentimentDirSampleModel, SentimentWindow } from './sentiment-dir-sample.model.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';
import { labelFromReturn, horizonDays, maxPriceGapMs, SENTIMENT_LABEL_VERSION } from './sentiment-dataset-labels.js';
import { SentimentPricePort } from './sentiment-price.adapter.js';
import { SentimentBinaryInferenceService } from '../binary/sentiment.binary.inference.service.js';

export type FinalizeStatus = 'CREATED' | 'SKIPPED' | 'RETRY' | 'FAILED';

export type FinalizeResult = {
  status: FinalizeStatus;
  reason?: string;
  sampleId?: string;
};

export interface DatasetAccumulatorConfig {
  graceMs: number;  // Buffer after window close before processing
}

const DEFAULT_GRACE_MS = 2 * 60 * 60 * 1000; // 2 hours

export class SentimentDatasetAccumulator {
  private readonly graceMs: number;

  constructor(
    private readonly pricePort: SentimentPricePort,
    config: Partial<DatasetAccumulatorConfig> = {}
  ) {
    this.graceMs = config.graceMs ?? DEFAULT_GRACE_MS;
  }

  /**
   * Normalize asOf to UTC seconds (remove ms)
   */
  private normalizeAsOf(asOf: Date): Date {
    return new Date(Math.floor(asOf.getTime() / 1000) * 1000);
  }

  /**
   * Map window from aggregate (24H) to dataset format (24H)
   * Aggregates use 24H, samples also use 24H
   */
  private mapWindow(window: string): SentimentWindow {
    if (window === '24H' || window === '1D') return '24H';
    if (window === '7D') return '7D';
    if (window === '30D') return '30D';
    return '7D'; // fallback
  }

  /**
   * Finalize a single sample from an aggregate snapshot.
   * 
   * Algorithm (spec-compliant):
   * 1. Normalize asOf to UTC seconds
   * 2. Check window has closed (now >= closeAt + grace)
   * 3. Load aggregate snapshot
   * 4. Validate aggregate is not empty
   * 5. Get prices at asOf and closeAt
   * 6. Validate price gap tolerance
   * 7. Compute return and label
   * 8. Atomic upsert sample
   * 
   * Modes:
   * - 'live': Only finalize if window has matured (production mode)
   * - 'backfill': Finalize historical data immediately if window has passed
   */
  async finalizeSample(args: {
    symbol: string;
    window: SentimentWindow;
    asOf: Date;
    mode?: 'live' | 'backfill';
  }): Promise<FinalizeResult> {
    const now = new Date();
    const mode = args.mode ?? 'live';

    // Step 0: Calculate closeAt based on original asOf
    const days = horizonDays(args.window);
    const closeAt = new Date(args.asOf.getTime() + days * 86400_000);

    // Step 1: Maturity guard
    if (mode === 'live') {
      // LIVE: Standard grace period check
      if (now.getTime() < closeAt.getTime() + this.graceMs) {
        return { status: 'SKIPPED', reason: 'NOT_MATURED' };
      }
    } else {
      // BACKFILL: Allow if closeAt is in the past (no grace needed)
      // Critical: closeAt must be in the past to avoid future leak
      if (closeAt.getTime() > now.getTime()) {
        return { status: 'SKIPPED', reason: 'BACKFILL_FUTURE_WINDOW' };
      }
    }

    // Step 2: Load aggregate snapshot
    // Map window format (aggregates use 24H/7D/30D)
    const aggWindow = args.window === '24H' ? '24H' : args.window;
    
    // Use original asOf for query (not normalized) since DB stores with milliseconds
    const agg = await SentimentAggregateModel.findOne({
      symbol: args.symbol,
      window: aggWindow,
      asOf: args.asOf, // Use original asOf
    }).lean();

    if (!agg) {
      return { status: 'SKIPPED', reason: 'AGGREGATE_NOT_FOUND' };
    }

    // Use normalized asOf for sample key (to avoid ms variations creating duplicates)
    const asOfKey = this.normalizeAsOf(args.asOf);

    // Step 3: Validate non-empty
    const eventsCount = agg.eventsCount ?? 0;
    if (eventsCount <= 0) {
      return { status: 'SKIPPED', reason: 'EMPTY_AGGREGATE' };
    }

    // Step 4: Get prices
    const p0 = await this.pricePort.getClosePriceAt(args.symbol, asOfKey);
    const p1 = await this.pricePort.getClosePriceAt(args.symbol, closeAt);

    if (!p0 || !p1) {
      return { status: 'RETRY', reason: 'PRICE_MISSING' };
    }

    // Step 5: Gap guard
    const gap0 = Math.abs(p0.ts.getTime() - asOfKey.getTime());
    const gap1 = Math.abs(p1.ts.getTime() - closeAt.getTime());
    const maxGap = maxPriceGapMs(args.window);

    if (gap0 > maxGap || gap1 > maxGap) {
      return { status: 'RETRY', reason: 'PRICE_GAP_TOO_LARGE' };
    }

    const price0 = Number(p0.price);
    const price1 = Number(p1.price);

    if (!Number.isFinite(price0) || !Number.isFinite(price1) || price0 <= 0 || price1 <= 0) {
      return { status: 'FAILED', reason: 'INVALID_PRICE' };
    }

    // Step 6: Compute return and label
    const returnPct = (price1 - price0) / price0;
    const label = labelFromReturn(args.window, returnPct);

    // Step 6.5: Get ML snapshot (for equity tracking)
    let mlSnapshot: { pUp: number; action: string; confidence: number; modelId: string } | undefined;
    try {
      const ml = await SentimentBinaryInferenceService.infer({
        window: args.window,
        sampleLike: {
          symbol: args.symbol,
          asOf: asOfKey,
          bias: agg.bias ?? 0,
          score: agg.score ?? 0.5,
          weightedScore: agg.weightedScore ?? agg.score ?? 0.5,
          weightedConfidence: agg.weightedConfidence ?? agg.confidence ?? 0.5,
          eventsCount: agg.eventsCount ?? 0,
          authorScoreMean: agg.authorScoreMean ?? 0.5,
          influenceMean: agg.influenceMean ?? 0.5,
          botProbMean: agg.botProbMean ?? 0.5,
        },
      });

      mlSnapshot = {
        pUp: ml.pUp,
        action: ml.action,
        confidence: ml.confidence,
        modelId: ml.meta.modelId,
      };
    } catch {
      // ML not ready or model missing — continue without
      mlSnapshot = undefined;
    }

    // Step 7: Build payload (BLOCK 2 Production Spec)
    const quality = eventsCount < 3 ? 'LOW_VOLUME' : 'OK';
    const volume = eventsCount;
    const connectionsWeight = (agg.authorScoreMean ?? 0.5) * (agg.influenceMean ?? 0.5);

    const payload = {
      symbol: args.symbol,
      window: args.window,
      asOf: asOfKey,

      // INPUT snapshot (known at asOf)
      score: agg.score ?? 0,
      bias: agg.bias ?? 0,
      confidence: agg.weightedConfidence ?? agg.confidence ?? 0,
      volume,
      connectionsWeight,
      eventsCount,
      
      // ML Features (BLOCK 3)
      authorScoreMean: agg.authorScoreMean,
      influenceMean: agg.influenceMean,
      botProbMean: agg.botProbMean,
      weightedScore: agg.weightedScore,
      weightedConfidence: agg.weightedConfidence,

      // Prices
      priceAtAsOf: price0,
      priceAtHorizonClose: price1,
      forwardReturnPct: returnPct,

      // Label
      label,
      labelVersion: SENTIMENT_LABEL_VERSION,
      finalizedAt: now,
      quality,

      // ML snapshot (for equity tracking)
      ml: mlSnapshot,
    };

    // Step 8: Atomic upsert (with labelVersion for versioned samples)
    try {
      const res = await SentimentDirSampleModel.updateOne(
        { 
          symbol: args.symbol, 
          window: args.window, 
          asOf: asOfKey,
          labelVersion: SENTIMENT_LABEL_VERSION,
        },
        { $setOnInsert: payload },
        { upsert: true }
      );

      if (res.upsertedCount === 1) {
        return { status: 'CREATED', sampleId: String(res.upsertedId) };
      }

      return { status: 'SKIPPED', reason: 'DUPLICATE_ALREADY_EXISTS' };
    } catch (err: any) {
      // Unique key violation (race condition)
      if (err?.code === 11000) {
        return { status: 'SKIPPED', reason: 'DUPLICATE_ALREADY_EXISTS' };
      }

      console.error('[DatasetAccumulator] Unexpected error:', err);
      return { status: 'FAILED', reason: 'UNHANDLED_ERROR' };
    }
  }

  /**
   * Get grace period in milliseconds
   */
  getGraceMs(): number {
    return this.graceMs;
  }
}
